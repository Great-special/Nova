# ============================================================
# nova/brain.py  —  AI Brain (OpenRouter free → Gemini free)
# ============================================================
"""
Provider strategy:
  1. OpenRouter is PRIMARY. Free-tier model slugs on OpenRouter rotate and
     get rate-limited often, so we keep a ranked CANDIDATE LIST of live
     ':free' models (fetched from OpenRouter's /models endpoint) and try
     them in order. The first model that responds successfully is PINNED
     for the rest of the session — we don't round-robin once something
     is working.
  2. If every candidate in that list fails (capped at MAX_OPENROUTER_TRIES
     models per request, to bound latency), we fall through to Gemini.
  3. If Gemini also fails, we return a friendly "unavailable" message.

"Failing" = ANY HTTP error (404 model gone, 429 rate-limited, 503 overloaded,
etc.) — we don't retry-with-delay on a single model; we just move on to the
next candidate immediately. This keeps behaviour simple and bounded.
"""
import os
import json
import urllib.request
import urllib.error

from config import (
    GEMINI_API_KEY, GEMINI_MODEL,
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
)

# ── System prompt that shapes Nova's personality ───────────
SYSTEM_PROMPT = """You are Nova, a concise, friendly personal assistant running on Windows.
You help the user with information, answer questions, and explain things clearly.
Keep responses SHORT (2-4 sentences max) unless the user explicitly asks for detail.
You are NOT controlling the computer directly — your role is to provide intelligent, 
conversational answers. Separate skill modules handle app launching, music, weather, etc.
Never make up facts. If unsure, say so."""

MAX_OPENROUTER_TRIES = 5   # cap on how many free models we'll cycle through per request

# Curated, reasonably capable free models to prefer if they're live —
# checked against the real-time list, not assumed to exist.
PREFERRED_OPENROUTER_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemini-2.0-flash-exp:free",
    "deepseek/deepseek-chat:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
]

_conversation_history = []        # rolling context for multi-turn chat
_pinned_openrouter_model = None   # the model that's working this session — sticky once set
_openrouter_candidates_cache = None  # cached ranked list of live free models for this session
_resolved_gemini_model = None     # cache: discovered working Gemini model (only used on 404)


# ══════════════════════════════════════════════════════════
#  OPENROUTER — candidate discovery
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

        # Preferred models first (if they're actually live), then any
        # other live free models as further fallback options.
        ranked = [m for m in PREFERRED_OPENROUTER_MODELS if m in live_free]
        ranked += [m for m in live_free if m not in ranked]

        _openrouter_candidates_cache = ranked
        print(f"[Brain/OpenRouter] {len(ranked)} live free models available.")
        return ranked

    except Exception as e:
        print(f"[Brain/OpenRouter] Could not fetch model list: {e}")
        # Fall back to the curated list and hope some of them are live
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
    rest of the session (no further switching while it keeps working).
    """
    global _pinned_openrouter_model

    if OPENROUTER_API_KEY == "YOUR_OPENROUTER_API_KEY":
        return None   # not configured

    # If we already have a model that's working this session, use it first.
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
            _pinned_openrouter_model = model   # stick with this one going forward
            print(f"[Brain/OpenRouter] Pinned '{model}' for this session.")
            return result

    print(f"[Brain/OpenRouter] All {min(len(candidates), MAX_OPENROUTER_TRIES)} attempted models failed.")
    return None


# ══════════════════════════════════════════════════════════
#  GEMINI — fallback brain
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


def _call_gemini(user_message: str) -> str | None:
    """Call Google Gemini free tier via REST. Retries once with an
    auto-discovered model name if the configured one 404s. Does NOT
    retry on 429/503 — those mean Gemini itself is overloaded, and since
    Gemini is now the fallback, we just give up and surface the failure."""
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        return None   # not configured

    model_to_use = _resolved_gemini_model or GEMINI_MODEL

    try:
        # Gemini uses "model" for the assistant's turn, not "assistant" —
        # translate our internal OpenAI-style history into Gemini's roles.
        contents = []
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
                return _call_gemini(user_message)   # retry once with discovered model
        print(f"[Brain/Gemini] Error {e.code}: {body}")
        return None

    except Exception as e:
        print(f"[Brain/Gemini] Error: {e}")
        return None


# ══════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════
def ask(user_message: str) -> str:
    """
    Send a message to the AI brain.
    Tries OpenRouter first (cycling free models as needed), then Gemini,
    then returns a friendly fallback message if both are unavailable.
    """
    answer = _call_openrouter(user_message)
    if answer is None:
        print("[Brain] OpenRouter exhausted, trying Gemini …")
        answer = _call_gemini(user_message)

    if answer is None:
        answer = (
            "I'm sorry, both my AI providers are unavailable right now — "
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