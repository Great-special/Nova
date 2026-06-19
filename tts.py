# ============================================================
# nova/tts.py  —  Text-to-Speech  (gTTS → pyttsx3 fallback)
# ============================================================
import os
import sys
import tempfile
import threading

from config import TTS_ENGINE

# ── lazy imports ───────────────────────────────────────────
_pyttsx3_engine = None
_pygame_ready    = False


def _init_pyttsx3():
    global _pyttsx3_engine
    if _pyttsx3_engine is None:
        import pyttsx3
        _pyttsx3_engine = pyttsx3.init()
        _pyttsx3_engine.setProperty("rate", 175)
        _pyttsx3_engine.setProperty("volume", 1.0)
    return _pyttsx3_engine


def _init_pygame():
    global _pygame_ready
    if not _pygame_ready:
        import pygame
        pygame.mixer.init()
        _pygame_ready = True


# ── gTTS path ──────────────────────────────────────────────
def _speak_gtts(text: str) -> bool:
    """Returns True on success, False on any failure."""
    try:
        from gtts import gTTS
        import pygame

        _init_pygame()

        tts = gTTS(text=text, lang="en", slow=False)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name
        tts.save(tmp_path)

        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

        pygame.mixer.music.unload()
        os.remove(tmp_path)
        return True

    except Exception as e:
        print(f"[TTS/gTTS] Failed: {e}")
        return False


# ── pyttsx3 path ───────────────────────────────────────────
def _speak_pyttsx3(text: str):
    engine = _init_pyttsx3()
    engine.say(text)
    engine.runAndWait()


# ── Public API ─────────────────────────────────────────────
def speak(text: str):
    """Speak text aloud and also print it to console."""
    print(f"\n🔊 Nova: {text}\n")

    engine = TTS_ENGINE.lower()

    if engine == "gtts":
        if not _speak_gtts(text):
            print("[TTS] gTTS failed, trying pyttsx3 …")
            _speak_pyttsx3(text)

    elif engine == "pyttsx3":
        _speak_pyttsx3(text)

    else:  # "auto" — try gTTS, fall back
        if not _speak_gtts(text):
            print("[TTS] Falling back to pyttsx3 …")
            _speak_pyttsx3(text)
        