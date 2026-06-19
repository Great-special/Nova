# ============================================================
# nova/router.py  —  Intent detection and command routing
# ============================================================
"""
The router sits between STT and skills/brain.
It uses simple keyword matching (no LLM needed for routing —
fast, offline, deterministic) to decide WHICH skill to call.
The AI brain is only invoked for open-ended questions.
"""

import re
from typing import Callable

import skills
import brain


# ── Helpers ────────────────────────────────────────────────
def _extract_after(text: str, *triggers) -> str:
    """Return text after the first matching trigger phrase."""
    for t in triggers:
        idx = text.find(t)
        if idx != -1:
            return text[idx + len(t):].strip()
    return text.strip()


def _extract_city(text: str) -> str:
    """Try to pull a city name from weather commands."""
    for prep in (" in ", " for ", " at "):
        if prep in text:
            return text.split(prep, 1)[-1].strip()
    return ""


def _extract_ticker(text: str) -> str:
    """Pull a stock ticker / company name from the command."""
    for trigger in ("stock", "share", "price of", "quote for", "ticker"):
        text = text.replace(trigger, "")
    # If looks like a ticker (1-5 uppercase letters), use it;
    # otherwise return the cleaned text for the browser search.
    cleaned = text.strip()
    words   = cleaned.split()
    if words and re.fullmatch(r"[A-Za-z]{1,5}", words[-1]):
        return words[-1].upper()
    return cleaned


def _extract_youtube_query(text: str) -> str:
    """Pull the search terms out of common YouTube commands."""
    query = re.sub(r"\b(on\s+)?youtube\b", "", text).strip()

    for trigger in ("search for", "search", "find", "play", "put on"):
        if query.startswith(trigger):
            query = query[len(trigger):].strip()
            break

    if query.startswith("for "):
        query = query[4:].strip()

    return query


# ── Intent patterns ────────────────────────────────────────
# Each entry: (list_of_trigger_keywords, handler_function)
# Order matters — more specific patterns first.

def route(command: str) -> str:
    """
    Detect intent from command text and call the appropriate skill.
    Returns the response string.
    """
    cmd = command.lower().strip()

    # ── EXIT / QUIT ────────────────────────────────────────
    if any(w in cmd for w in ("goodbye", "bye nova", "quit", "exit", "shut down nova", "stop nova")):
        return "__EXIT__"   # sentinel handled by main loop

    # ── TIME ──────────────────────────────────────────────
    if any(w in cmd for w in ("what time", "current time", "what's the time", "tell me the time")):
        return skills.get_time()

    # ── OPEN APP ──────────────────────────────────────────
    if cmd.startswith("open "):
        app = _extract_after(cmd, "open ")
        return skills.open_app(app)

    if cmd.startswith("launch "):
        app = _extract_after(cmd, "launch ")
        return skills.open_app(app)

    if "open " in cmd and any(a in cmd for a in ("notepad","chrome","firefox","excel","word","calculator","discord","spotify","vlc")):
        app = _extract_after(cmd, "open ")
        return skills.open_app(app)

    # ── MUSIC — YouTube specific ───────────────────────────
    if "youtube" in cmd and any(w in cmd for w in ("play", "search", "find", "put on")):
        query = _extract_youtube_query(cmd)
        return skills.play_youtube(query)

    # ── MUSIC — local ─────────────────────────────────────
    if "local" in cmd and any(w in cmd for w in ("play", "music")):
        query = _extract_after(cmd, "local music", "play local", "locally")
        return skills.play_local_music(query)

    # ── MUSIC — general ───────────────────────────────────
    if any(cmd.startswith(t) for t in ("play ", "listen to ", "put on ")):
        return skills.handle_music(cmd)

    if "play music" in cmd or "play some music" in cmd:
        return skills.handle_music(cmd)

    # ── WEATHER ───────────────────────────────────────────
    if any(w in cmd for w in ("weather", "temperature", "forecast", "rain", "humidity")):
        city = _extract_city(cmd)
        return skills.get_weather(city)

    # ── STOCKS ────────────────────────────────────────────
    if any(w in cmd for w in ("stock", "share price", "ticker", "nasdaq", "nyse", "market cap")):
        ticker = _extract_ticker(cmd)
        return skills.lookup_stock(ticker)

    # ── WEB SEARCH ────────────────────────────────────────
    if any(cmd.startswith(t) for t in (
        "search ", "search for ", "google ", "look up ", "look up ",
        "find information", "research ", "browse "
    )):
        query = _extract_after(
            cmd, "search for", "search", "google", "look up", "find information about",
            "research", "browse"
        )
        return skills.web_search(query)

    if "on the web" in cmd or "on google" in cmd or "online" in cmd:
        query = re.sub(r"\b(search|find|look up|on the web|on google|online)\b", "", cmd).strip()
        return skills.web_search(query)

    # ── VOLUME ────────────────────────────────────────────
    if "volume" in cmd:
        numbers = re.findall(r"\d+", cmd)
        if numbers:
            return skills.set_volume(int(numbers[0]))
        if "up" in cmd:
            return skills.set_volume(70)
        if "down" in cmd or "lower" in cmd:
            return skills.set_volume(30)
        if "mute" in cmd:
            return skills.set_volume(0)

    # ── FALLBACK — AI brain ───────────────────────────────
    return brain.ask(command)
