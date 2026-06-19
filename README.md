# Nova

Nova is a small Windows voice assistant. It listens for a wake word, hears your command, routes it to a skill or the AI brain, then speaks back.

## Project Files

```text
main.py                   Entry point
config.py                 Settings and API keys
stt.py                    Speech-to-text and wake-word detection
tts.py                    Text-to-speech
brain.py                  AI fallback for open-ended questions
skills.py                 App, music, weather, stock, web, and volume actions
router.py                 Command routing
Ubiquitous_language.md    Shared project terms
tests/                    Unit tests
```

## Install

```bash
pip install -r requirements.txt
```

On Windows, PyAudio can need an extra step:

```bash
pip install pipwin
pipwin install pyaudio
```

## Configure

Edit `config.py`.

```python
WAKE_WORD = "nova"
DEFAULT_CITY = "Lagos"
```

For AI answers, set one of these environment variables:

```powershell
$env:GEMINI_API_KEY = "your_key_here"
$env:OPENROUTER_API_KEY = "your_key_here"
```

For weather, set:

```powershell
$env:OPENWEATHER_API_KEY = "your_key_here"
```

## Run

```bash
python main.py
```

## Use Nova

Say the wake word first:

```text
Nova
```

When Nova says, "Yes? I'm listening," say your command.

You can also speak in one breath:

```text
Nova open Chrome
```

## Example Commands

| What you say | What Nova does |
|---|---|
| `Nova open Chrome` | Opens Chrome |
| `Nova open Notepad` | Opens Notepad |
| `Nova play Afrobeats on YouTube` | Opens a YouTube search |
| `Nova play some music` | Plays local music or searches YouTube |
| `Nova what's the weather in Abuja?` | Gets weather for Abuja |
| `Nova what's the weather?` | Gets weather for your default city |
| `Nova stock AAPL` | Opens Yahoo Finance |
| `Nova search for Python tutorials` | Opens a Google search |
| `Nova what time is it?` | Tells the time |
| `Nova what is machine learning?` | Asks the AI brain |
| `Nova goodbye` | Shuts Nova down |

## Troubleshooting

| Problem | Try this |
|---|---|
| `No module named 'pyaudio'` | Run `pipwin install pyaudio` |
| `No module named 'whisper'` | Install `openai-whisper` or set `STT_ENGINE = "google"` |
| Wake word not detected | Say `nova` clearly, lower background noise, or try `STT_ENGINE = "google"` |
| TTS not working | Check your speakers or set `TTS_ENGINE = "pyttsx3"` |
| Weather returns an API error | Add a valid OpenWeatherMap key |
| AI says keys are missing | Add a Gemini or OpenRouter key |
