# ============================================================
# nova/skills.py  —  All action skills Nova can perform
# ============================================================
import os
import sys
import subprocess
import webbrowser
import urllib.parse
import urllib.request
import json
import glob
import platform

from config import (
    KNOWN_APPS, LOCAL_MUSIC_DIR,
    OPENWEATHER_API_KEY, DEFAULT_CITY,
    PREFERRED_BROWSER,
)


# ══════════════════════════════════════════════════════════
#  HELPER: open URL in browser
# ══════════════════════════════════════════════════════════
def _open_url(url: str):
    if PREFERRED_BROWSER:
        try:
            browser = webbrowser.get(PREFERRED_BROWSER)
            browser.open(url)
            return
        except Exception:
            pass
    webbrowser.open(url)


# ══════════════════════════════════════════════════════════
#  SKILL 1 — OPEN APP
# ══════════════════════════════════════════════════════════
def open_app(app_name: str) -> str:
    """
    Try to open an app by name.
    Strategy: KNOWN_APPS dict → shutil.which → Windows Start search.
    """
    import shutil

    name_lower = app_name.lower().strip()

    # 1) Known apps dict
    exe = KNOWN_APPS.get(name_lower)
    if exe:
        try:
            subprocess.Popen(exe, shell=True)
            return f"Opening {app_name} …"
        except Exception as e:
            return f"Found {app_name} but couldn't open it: {e}"

    # 2) Try as raw exe name via PATH
    exe_guess = name_lower.replace(" ", "") + ".exe"
    if shutil.which(exe_guess):
        try:
            subprocess.Popen(exe_guess, shell=True)
            return f"Opening {app_name} …"
        except Exception as e:
            return f"Tried to open {exe_guess} but failed: {e}"

    # 3) Last resort: open Windows Start Menu search
    _open_url(f"shell:AppsFolder")
    subprocess.Popen(f'explorer shell:AppsFolder', shell=True)
    return (
        f"I couldn't find '{app_name}' automatically. "
        "I've opened your Apps folder — you can search from there."
    )


# ══════════════════════════════════════════════════════════
#  SKILL 2 — PLAY MUSIC (YouTube or local)
# ══════════════════════════════════════════════════════════
def play_youtube(query: str) -> str:
    """Search YouTube and open the results page."""
    encoded = urllib.parse.quote(query)
    url = f"https://www.youtube.com/results?search_query={encoded}"
    _open_url(url)
    return f"Searching YouTube for: {query}"


def play_local_music(query: str) -> str:
    """
    Search LOCAL_MUSIC_DIR for a matching audio file and open it.
    Supports mp3, flac, wav, ogg, m4a.
    """
    extensions = ("*.mp3", "*.flac", "*.wav", "*.ogg", "*.m4a")
    matches = []

    for ext in extensions:
        pattern = os.path.join(LOCAL_MUSIC_DIR, "**", ext)
        matches.extend(glob.glob(pattern, recursive=True))

    if not matches:
        return f"No music files found in {LOCAL_MUSIC_DIR}."

    # Simple fuzzy match: prefer files whose name contains the query words
    query_words = query.lower().split()
    scored = []
    for path in matches:
        filename = os.path.basename(path).lower()
        score = sum(1 for w in query_words if w in filename)
        scored.append((score, path))

    scored.sort(key=lambda x: -x[0])
    best_score, best_path = scored[0]

    if best_score == 0:
        # No match — play first file found
        best_path = matches[0]

    os.startfile(best_path)
    return f"Playing: {os.path.basename(best_path)}"


def handle_music(command: str) -> str:
    """
    Route music command to YouTube or local depending on keywords.
    'play X on youtube' → YouTube
    'play X locally' / 'play local X' → local
    Otherwise → try local first, fall back to YouTube.
    """
    cmd = command.lower()

    # Strip leading trigger words
    for trigger in ("play music", "play", "listen to", "put on"):
        if cmd.startswith(trigger):
            cmd = cmd[len(trigger):].strip()
            break

    if "youtube" in cmd:
        query = cmd.replace("youtube", "").replace("on", "").strip()
        return play_youtube(query)

    if "local" in cmd:
        query = cmd.replace("local", "").strip()
        return play_local_music(query)

    # Default: try local first
    result = play_local_music(cmd)
    if "No music files" in result or "Playing:" not in result:
        return play_youtube(cmd)
    return result


# ══════════════════════════════════════════════════════════
#  SKILL 3 — WEATHER
# ══════════════════════════════════════════════════════════
def get_weather(city: str = "") -> str:
    city = city.strip() or DEFAULT_CITY

    if OPENWEATHER_API_KEY == "YOUR_OPENWEATHER_API_KEY":
        return (
            "Weather API key not configured. "
            "Please add your OpenWeatherMap key in config.py."
        )

    try:
        encoded_city = urllib.parse.quote(city)
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={encoded_city}&appid={OPENWEATHER_API_KEY}&units=metric"
        )
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())

        desc    = data["weather"][0]["description"].capitalize()
        temp    = data["main"]["temp"]
        feels   = data["main"]["feels_like"]
        humidity= data["main"]["humidity"]
        wind    = data["wind"]["speed"]

        return (
            f"Weather in {city}: {desc}. "
            f"Temperature {temp:.1f}°C, feels like {feels:.1f}°C. "
            f"Humidity {humidity}%, wind {wind} m/s."
        )

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"City '{city}' not found. Try a different city name."
        return f"Weather API error: {e}"
    except Exception as e:
        return f"Couldn't fetch weather: {e}"


# ══════════════════════════════════════════════════════════
#  SKILL 4 — STOCKS (open browser)
# ══════════════════════════════════════════════════════════
def lookup_stock(ticker: str) -> str:
    """Open Yahoo Finance for the given ticker symbol."""
    ticker = ticker.upper().strip()
    url = f"https://finance.yahoo.com/quote/{ticker}"
    _open_url(url)
    return f"Opening Yahoo Finance for {ticker} …"


# ══════════════════════════════════════════════════════════
#  SKILL 5 — WEB SEARCH (open browser)
# ══════════════════════════════════════════════════════════
def web_search(query: str) -> str:
    """Open Google search results for the given query."""
    encoded = urllib.parse.quote(query)
    url = f"https://www.google.com/search?q={encoded}"
    _open_url(url)
    return f"Searching the web for: {query}"


# ══════════════════════════════════════════════════════════
#  SKILL 6 — SYSTEM CONTROLS
# ══════════════════════════════════════════════════════════
def set_volume(level: int) -> str:
    """Set system volume 0–100 using PowerShell (Windows only)."""
    level = max(0, min(100, level))
    script = (
        f"$obj = New-Object -ComObject WScript.Shell; "
        f"1..50 | ForEach-Object {{ $obj.SendKeys([char]174) }}; "   # mute first
        f"$vol = {level}; "
        f"$steps = [math]::Round($vol / 2); "
        f"1..$steps | ForEach-Object {{ $obj.SendKeys([char]175) }}"  # volume up
    )
    subprocess.run(["powershell", "-Command", script], capture_output=True)
    return f"Volume set to approximately {level}%."


def get_time() -> str:
    from datetime import datetime
    now = datetime.now()
    return f"The current time is {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}."
