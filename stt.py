# ============================================================
# nova/stt.py - Speech-to-text and wake-word detection
# ============================================================
import io
import re

import speech_recognition as sr

from config import (
    AMBIENT_DURATION,
    MIC_PHRASE_LIMIT,
    MIC_TIMEOUT,
    STT_ENGINE,
    WAKE_WORD,
    WHISPER_MODEL_SIZE,
)

_recognizer = sr.Recognizer()
_microphone = sr.Microphone()
_whisper_model = None


def _load_whisper():
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper

            print(f"[STT] Loading Whisper '{WHISPER_MODEL_SIZE}' model ...")
            _whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
            print("[STT] Whisper ready")
        except Exception as e:
            print(f"[STT] Whisper unavailable: {e}")
            _whisper_model = False

    return _whisper_model if _whisper_model else None


def _transcribe_whisper(audio: sr.AudioData) -> str | None:
    model = _load_whisper()
    if model is None:
        return None

    try:
        import soundfile as sf

        wav_bytes = audio.get_wav_data()
        data, _ = sf.read(io.BytesIO(wav_bytes), dtype="float32")
        if data.ndim > 1:
            data = data.mean(axis=1)

        result = model.transcribe(data, language="en", fp16=False)
        return result["text"].strip()
    except Exception as e:
        print(f"[STT/Whisper] Error: {e}")
        return None


def _transcribe_google(audio: sr.AudioData) -> str | None:
    try:
        return _recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        print(f"[STT/Google] API error: {e}")
        return None


def _transcribe(audio: sr.AudioData) -> str:
    """Run the configured STT engine with fallback."""
    engine = STT_ENGINE.lower()
    text = None

    if engine == "whisper":
        text = _transcribe_whisper(audio)
        if text is None:
            print("[STT] Whisper failed, trying Google ...")
            text = _transcribe_google(audio)
    elif engine == "google":
        text = _transcribe_google(audio)
    else:
        if _load_whisper():
            text = _transcribe_whisper(audio)
        if text is None:
            text = _transcribe_google(audio)

    final_text = text or ""
    print(f"[STT] Transcription result: '{final_text}'")
    return final_text.lower().strip()


def calibrate(source=None):
    """Adjust for ambient noise once at startup."""
    if source is None:
        with _microphone as mic_source:
            return calibrate(source=mic_source)

    print("[STT] Calibrating microphone ...")

    _recognizer.adjust_for_ambient_noise(source, duration=AMBIENT_DURATION)
    _recognizer.dynamic_energy_threshold = True
    print("[STT] Calibration complete.")
    print("[STT] Microphone ready")


def listen_once(source=None, timeout=MIC_TIMEOUT, phrase_limit=MIC_PHRASE_LIMIT) -> str:
    """
    Listen for one utterance and return transcribed text.
    Returns "" if nothing was heard or the audio was unintelligible.
    """
    if source is None:
        with _microphone as mic_source:
            return listen_once(
                source=mic_source,
                timeout=timeout,
                phrase_limit=phrase_limit,
            )

    try:
        print(f"[STT] Listening for speech (timeout={timeout}s, phrase_limit={phrase_limit}s) ...")
        audio = _recognizer.listen(
            source,
            timeout=timeout,
            phrase_time_limit=phrase_limit,
        )
        print(f"[STT] Audio captured, transcribing {audio.get_wav_data().__sizeof__()} bytes ...")
        return _transcribe(audio)
    except sr.WaitTimeoutError:
        return ""
    except Exception as e:
        print(f"[STT] listen_once error: {e}")
        return ""


def extract_wake_command(text: str, wake_word: str = WAKE_WORD) -> str | None:
    """
    Return the command spoken after the wake word.
    Returns "" when only the wake word was heard, and None when the wake word
    was not heard.
    """
    if not text:
        return None

    normalized_text = text.lower().strip()
    normalized_wake = wake_word.lower().strip()
    wake_pattern = r"(?<!\w)" + r"\s+".join(
        re.escape(part) for part in normalized_wake.split()
    ) + r"(?!\w)"

    match = re.search(wake_pattern, normalized_text)
    if not match:
        return None

    return normalized_text[match.end():].strip(" \t,.;:!?-")


def wait_for_wake_word(source=None) -> str:
    """
    Block until the wake word is detected.
    Return any command spoken in the same utterance after the wake word.
    Return "" when only the wake word was heard.
    """
    print(f'[STT] Listening for wake word: "{WAKE_WORD}" ...')

    while True:
        text = listen_once(source=source, timeout=MIC_TIMEOUT, phrase_limit=MIC_PHRASE_LIMIT)
        command = extract_wake_command(text)
        if command is not None:
            print(f"[STT] Wake word detected! (heard: '{text}')")
            return command
