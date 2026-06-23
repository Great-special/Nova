#!/usr/bin/env python
# ============================================================
# Mira/main.py - Mira Personal Assistant entry point
# ============================================================
"""
Usage:
    python main.py

Flow:
    1. Startup checks and mic calibration
    2. Wait for the wake word
    3. Use an immediate command if one was spoken after the wake word
    4. Otherwise ask for the command and listen once
    5. Route the command, speak the response, and return to step 2
"""

import os
import sys

import pyfiglet

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import MIC_TIMEOUT, WAKE_WORD, MIC_PHRASE_LIMIT, DEFAULT_CITY, USER
from router import route
import skills
from stt import calibrate, listen_once, wait_for_wake_word
from tts import speak

BANNER = r"""
  Personal AI Assistant - Windows Edition
  Say "{wake}" to activate.
  Type 'quit' and press Enter to exit.
""".format(wake=WAKE_WORD.title())


    
    

def startup(source=None):
    from datetime import datetime
    now = datetime.now()

    ascii_banner = pyfiglet.figlet_format(WAKE_WORD, font="slant")

    if 0 < now.hour < 12:
        greet = f'Good morning, {USER} ' + f"The current time is {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}."

    elif 12 <= now.hour <= 16:
        greet = f'Good afternoon, {USER} ' + f"The current time is {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}."

    else:
        greet = f'Good evening, {USER} ' + f"The current time is {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}."

    print(ascii_banner)
    print(BANNER)
    print("=" * 50)
    print("Initialising M.I.R.A ...")

    calibrate(source)

    speak(f"Mira is online. Say {WAKE_WORD} to give me a command.")
    print("=" * 50)
    speak(greet)

    # Network-dependent lookups happen AFTER the user already has audio
    # feedback that Mira is alive, so launch doesn't feel like it's hung.
    weather_res = skills.get_weather(DEFAULT_CITY)
    speak(weather_res)

    world_news_res = skills.web_search("world news today", open_browser=False)
    speak(world_news_res)

    ai_news_res = skills.web_search("AI news today", open_browser=False)
    speak(ai_news_res)
    print("=" * 50)


def handle_command(command: str):
    print(f"[Mira] You said: {command}")

    response = route(command)
    if response == "__EXIT__":
        speak("Goodbye! Mira is shutting down.")
        print("\nMira stopped. Goodbye!\n")
        sys.exit(0)

    speak(response)


def main_loop(source=None):
    """
    Wait for the wake word, then route either the same-utterance command or
    the next utterance.
    """
    while True:
        try:
            command = wait_for_wake_word(source=source)

            if command:
                print(f"[Mira] Immediate command detected: {command}")
            else:
                speak("Yes? I'm listening.")
                print("[Mira] Listening for your command ...")
                command = listen_once(source=source, timeout=MIC_TIMEOUT, phrase_limit=MIC_PHRASE_LIMIT)

            if not command:
                speak("I didn't catch that. Please try again.")
                continue

            handle_command(command)

        except KeyboardInterrupt:
            speak("Goodbye! Mira is shutting down.")
            print("\nMira stopped. Goodbye!\n")
            sys.exit(0)

        except Exception as e:
            print(f"[Mira] Unexpected error: {e}")
            speak("Something went wrong. I'm still here. Please try again.")


if __name__ == "__main__":
    
    startup()
    main_loop()