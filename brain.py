# ============================================================
# nova/brain.py  —  AI Brain (Hugging Face → Gemini → OpenRouter)
# ============================================================
"""
Provider strategy (in order of priority):

  1. HUGGING FACE is PRIMARY. We keep a small curated list of real HF Hub
     model IDs (HF uses bare org/model IDs, optionally with a ':provider' 
     or ':cheapest'/':fastest' routing suffix).
     We verify each candidate is actually listed on HF's live /v1/models
     before trying it, then cycle through them immediately on any failure.
     The first one that succeeds is PINNED for the rest of the session.

  2. GEMINI is SECONDARY. If every HF candidate fails, we fall through to
     Google's Gemini free tier.

  3. OPENROUTER is TERTIARY (final fallback). If Gemini also fails, we fall
     through to OpenRouter's free-model cycling (same logic as before).

  4. If all three providers fail, we return a friendly "unavailable" message.

"Failing" = ANY HTTP error (404 model gone, 429 rate-limited, 503 overloaded,
etc.) — we don't retry-with-delay on a single model; we just move on to the
next candidate immediately. This keeps behaviour simple and bounded.
"""
import os
import json
import urllib.request
import urllib.error

from config import (
    HF_API_KEY, HF_BASE_URL,
    GEMINI_API_KEY, GEMINI_MODEL,
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    WAKE_WORD
)

# ── System prompt that shapes Nova's personality ───────────
SYSTEM_PROMPT = f"""You are {WAKE_WORD}, a Model for Intelligent Research and Automation.
You help the user with information, answer questions, and explain things clearly.

You are NOT controlling the computer directly — your role is to provide intelligent, 
conversational answers. Separate skill modules handle app launching, music, weather, etc.
Never make up facts. If unsure, say so. And search the internet."""

MAX_HF_TRIES = 3           # we only curate 3 HF candidates, try all of them
MAX_OPENROUTER_TRIES = 5   # cap on how many free OpenRouter models we'll cycle through

# Curated, real Hugging Face Hub model IDs — checked against the live
# https://router.huggingface.co/v1/models response on 2026-06-22.
# Bare ID (e.g. Llama-3.1-8B-Instruct below) lets HF auto-route to its
# ":fastest" provider; an explicit ":provider" or ":cheapest"/":fastest"
# suffix pins routing behaviour for that one model.
PREFERRED_HF_MODELS = [
    "deepseek-ai/DeepSeek-R1:novita",
    "meta-llama/Llama-3.1-8B-Instruct",
    "MiniMaxAI/MiniMax-M2.1:cheapest",
]

# Curated OpenRouter free models (unchanged from before)
PREFERRED_OPENROUTER_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "deepseek/deepseek-chat:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
]

_conversation_history = []        # rolling context for multi-turn chat

_pinned_hf_model = None           # HF model that's working this session — sticky once set
_hf_candidates_cache = None       # cached, live-verified HF candidate list for this session

_pinned_openrouter_model = None   # OpenRouter model that's working this session
_openrouter_candidates_cache = None  # cached ranked list of live free OpenRouter models

_resolved_gemini_model = None     # cache: discovered working Gemini model (only used on 404)


# ══════════════════════════════════════════════════════════
#  HUGGING FACE — primary brain
# ══════════════════════════════════════════════════════════
def _strip_suffix(model_id: str) -> str:
    """Strip a ':provider'/':cheapest'/':fastest' suffix for matching against
    the bare IDs returned by /v1/models."""
    return model_id.split(":")[0]


def _fetch_hf_candidates() -> list[str]:
    """
    Verify our curated HF model IDs are actually listed on HF's live
    /v1/models endpoint before using them. Cached for the session.
    If the live list can't be fetched, fall back to trying the curated
    list directly (better to attempt than to give up early).
    """
    global _hf_candidates_cache
    if _hf_candidates_cache is not None:
        return _hf_candidates_cache

    if HF_API_KEY == "YOUR_HF_API_KEY":
        _hf_candidates_cache = []
        return _hf_candidates_cache

    try:
        req = urllib.request.Request(
            f"{HF_BASE_URL}/models",
            headers={"Authorization": f"Bearer {HF_API_KEY}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        live_ids = {m["id"] for m in data.get("data", [])}

        verified = [
            candidate for candidate in PREFERRED_HF_MODELS
            if _strip_suffix(candidate) in live_ids
        ]

        if not verified:
            print("[Brain/HF] None of the curated models were found in the live list — "
                  "trying them directly anyway (list may be incomplete without full scope).")
            verified = list(PREFERRED_HF_MODELS)

        _hf_candidates_cache = verified
        print(f"[Brain/HF] {len(verified)} candidate model(s) ready to try.")
        return verified

    except Exception as e:
        print(f"[Brain/HF] Could not verify model list ({e}) — trying curated list directly.")
        _hf_candidates_cache = list(PREFERRED_HF_MODELS)
        return _hf_candidates_cache


def _call_hf_with_model(user_message: str, model: str) -> str | None:
    """Single attempt against one specific HF router model. Returns None on any failure."""
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in _conversation_history[-6:]:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": user_message})

        payload = json.dumps({
            "model": model,
            "messages": messages,
            "max_tokens": 500,
            "temperature": 0.7,
        }).encode()

        req = urllib.request.Request(
            f"{HF_BASE_URL}/chat/completions",
            data=payload,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {HF_API_KEY}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())

        return data["choices"][0]["message"]["content"].strip()

    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"[Brain/HF] '{model}' failed ({e.code}): {body}")
        return None

    except Exception as e:
        print(f"[Brain/HF] '{model}' failed: {e}")
        return None


def _call_hf(user_message: str) -> str | None:
    """
    Try Hugging Face candidates in order until one works, capped at
    MAX_HF_TRIES. Once a model succeeds, it's pinned for the rest of
    the session.
    """
    global _pinned_hf_model

    if HF_API_KEY == "YOUR_HF_API_KEY":
        return None   # not configured

    if _pinned_hf_model:
        result = _call_hf_with_model(user_message, _pinned_hf_model)
        if result is not None:
            return result
        print(f"[Brain/HF] Pinned model '{_pinned_hf_model}' just failed — unpinning.")
        _pinned_hf_model = None

    candidates = _fetch_hf_candidates()
    if not candidates:
        print("[Brain/HF] No candidates available to try.")
        return None

    for model in candidates[:MAX_HF_TRIES]:
        result = _call_hf_with_model(user_message, model)
        if result is not None:
            _pinned_hf_model = model
            print(f"[Brain/HF] Pinned '{model}' for this session.")
            return result

    print(f"[Brain/HF] All {min(len(candidates), MAX_HF_TRIES)} attempted models failed.")
    return None


# ══════════════════════════════════════════════════════════
#  GEMINI — secondary brain
# ══════════════════════════════════════════════════════════
def _discover_gemini_model() -> str | None:
    """
    If the configured GEMINI_MODEL 404s, ask Google's ListModels endpoint
    for a model that actually supports generateContent right now, and
    cache it for the rest of the session.
    """
    global _resolved_gemini_model
    if _resolved_gemini_model:
        return _resolved_gemini_model

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())

        candidates = [
            m["name"].split("/")[-1]
            for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]

        flash = [m for m in candidates if "flash" in m and "flash-lite" not in m]
        chosen = (flash or candidates or [None])[0]

        if chosen:
            print(f"[Brain/Gemini] Auto-discovered working model: {chosen}")
            _resolved_gemini_model = chosen
        return chosen

    except Exception as e:
        print(f"[Brain/Gemini] Model discovery failed: {e}")
        return None


def ask_gemini_only(user_message: str) -> str | None:
    """
    Public, standalone Gemini call with NO conversation history and NO
    fallback to HF/OpenRouter. Used by other modules (e.g. skills.web_search)
    that want a one-off factual answer without going through the full
    ask() chain or polluting the rolling chat history. Returns None on
    any failure — caller decides what to do next.
    """
    return _call_gemini(user_message, use_history=False)


def _call_gemini(user_message: str, use_history: bool = True) -> str | None:
    """Call Google Gemini free tier via REST. Retries once with an
    auto-discovered model name if the configured one 404s. Does NOT
    retry on 429/503 — those mean Gemini itself is overloaded, and since
    Gemini is a fallback here, we just give up and surface the failure."""
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        return None   # not configured

    model_to_use = _resolved_gemini_model or GEMINI_MODEL

    try:
        # Gemini uses "model" for the assistant's turn, not "assistant" —
        # translate our internal OpenAI-style history into Gemini's roles.
        contents = []
        if use_history:
            for turn in _conversation_history[-6:]:   # last 3 exchanges
                gemini_role = "model" if turn["role"] == "assistant" else "user"
                contents.append({"role": gemini_role, "parts": [{"text": turn["content"]}]})
        contents.append({"role": "user", "parts": [{"text": user_message}]})

        payload = json.dumps({
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": contents,
            "generationConfig": {"maxOutputTokens": 300, "temperature": 0.7},
        }).encode()

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_to_use}:generateContent?key={GEMINI_API_KEY}"
        )
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        if e.code == 404 and model_to_use == GEMINI_MODEL:
            print(f"[Brain/Gemini] '{model_to_use}' not found (404). Discovering a live model …")
            new_model = _discover_gemini_model()
            if new_model and new_model != model_to_use:
                return _call_gemini(user_message, use_history=use_history)   # retry once with discovered model
        print(f"[Brain/Gemini] Error {e.code}: {body}")
        return None

    except Exception as e:
        print(f"[Brain/Gemini] Error: {e}")
        return None


# ══════════════════════════════════════════════════════════
#  OPENROUTER — final fallback brain
# ══════════════════════════════════════════════════════════
def _fetch_openrouter_candidates() -> list[str]:
    """
    Fetch and rank the live ':free' models from OpenRouter.
    Cached for the session — we don't re-fetch on every call.
    """
    global _openrouter_candidates_cache
    if _openrouter_candidates_cache is not None:
        return _openrouter_candidates_cache

    try:
        req = urllib.request.Request(
            f"{OPENROUTER_BASE_URL}/models",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        live_free = {
            m["id"] for m in data.get("data", [])
            if m.get("id", "").endswith(":free")
        }

        ranked = [m for m in PREFERRED_OPENROUTER_MODELS if m in live_free]
        ranked += [m for m in live_free if m not in ranked]

        _openrouter_candidates_cache = ranked
        print(f"[Brain/OpenRouter] {len(ranked)} live free models available.")
        return ranked

    except Exception as e:
        print(f"[Brain/OpenRouter] Could not fetch model list: {e}")
        _openrouter_candidates_cache = list(PREFERRED_OPENROUTER_MODELS)
        return _openrouter_candidates_cache


def _call_openrouter_with_model(user_message: str, model: str) -> str | None:
    """Single attempt against one specific OpenRouter model. Returns None on any failure."""
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in _conversation_history[-6:]:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": user_message})

        payload = json.dumps({
            "model": model,
            "messages": messages,
            "max_tokens": 300,
            "temperature": 0.7,
        }).encode()

        req = urllib.request.Request(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            data=payload,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer":  "https://nova-assistant.local",
                "X-Title":       "Nova Personal Assistant",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        return data["choices"][0]["message"]["content"].strip()

    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"[Brain/OpenRouter] '{model}' failed ({e.code}): {body}")
        return None

    except Exception as e:
        print(f"[Brain/OpenRouter] '{model}' failed: {e}")
        return None


def _call_openrouter(user_message: str) -> str | None:
    """
    Try OpenRouter free models in order until one works, capped at
    MAX_OPENROUTER_TRIES. Once a model succeeds, it's pinned for the
    rest of the session.
    """
    global _pinned_openrouter_model

    if OPENROUTER_API_KEY == "YOUR_OPENROUTER_API_KEY":
        return None   # not configured

    if _pinned_openrouter_model:
        result = _call_openrouter_with_model(user_message, _pinned_openrouter_model)
        if result is not None:
            return result
        print(f"[Brain/OpenRouter] Pinned model '{_pinned_openrouter_model}' just failed — unpinning.")
        _pinned_openrouter_model = None

    candidates = _fetch_openrouter_candidates()
    if not candidates:
        print("[Brain/OpenRouter] No free models available to try.")
        return None

    for model in candidates[:MAX_OPENROUTER_TRIES]:
        result = _call_openrouter_with_model(user_message, model)
        if result is not None:
            _pinned_openrouter_model = model
            print(f"[Brain/OpenRouter] Pinned '{model}' for this session.")
            return result

    print(f"[Brain/OpenRouter] All {min(len(candidates), MAX_OPENROUTER_TRIES)} attempted models failed.")
    return None


# ══════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════
def ask(user_message: str) -> str:
    """
    Send a message to the AI brain.
    Tries Hugging Face first (cycling curated models as needed), then
    Gemini, then OpenRouter, then returns a friendly fallback message
    if all three are unavailable.
    """
    answer = _call_hf(user_message)

    if answer is None:
        print("[Brain] Hugging Face exhausted, trying Gemini …")
        answer = _call_gemini(user_message)

    if answer is None:
        print("[Brain] Gemini exhausted, trying OpenRouter …")
        answer = _call_openrouter(user_message)

    if answer is None:
        answer = (
            "I'm sorry, all my AI providers are unavailable right now — "
            "likely temporary overload on the free tiers. Please try again shortly."
        )

    # Update rolling history
    _conversation_history.append({"role": "user",      "content": user_message})
    _conversation_history.append({"role": "assistant",  "content": answer})

    # Keep history bounded (last 20 turns)
    if len(_conversation_history) > 20:
        _conversation_history[:] = _conversation_history[-20:]

    return answer


def reset_conversation():
    """Clear the rolling conversation history."""
    _conversation_history.clear()