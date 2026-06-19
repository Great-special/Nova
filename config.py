# ============================================================
# nova/config.py - Central configuration for Nova Assistant
# ============================================================
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Wake word
WAKE_WORD = "nova"

# AI brain
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "YOUR_OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Weather
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "YOUR_OPENWEATHER_API_KEY")
DEFAULT_CITY = "Lagos"

# Speech-to-text
# "whisper" = local Whisper model
# "google" = Google Speech Recognition
# "auto" = try Whisper first, then Google
STT_ENGINE = "google"
WHISPER_MODEL_SIZE = "base"

# Text-to-speech
# "gtts" = gTTS + pygame
# "pyttsx3" = offline TTS
# "auto" = try gTTS first, then pyttsx3
TTS_ENGINE = "auto"

# Apps known to Nova
KNOWN_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
    "vlc": "vlc.exe",
    "spotify": "spotify.exe",
    "vs code": "code.exe",
    "vscode": "code.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "discord": "discord.exe",
    "telegram": "telegram.exe",
    "whatsapp": "whatsapp.exe",
    "zoom": "zoom.exe",
}

# Local music folder
LOCAL_MUSIC_DIR = r"C:\Users\Public\Music"

# Browser
# Leave empty to use your system default browser.
PREFERRED_BROWSER = ""

# Listening settings
MIC_TIMEOUT = None
MIC_PHRASE_LIMIT = 180
AMBIENT_DURATION = 1
