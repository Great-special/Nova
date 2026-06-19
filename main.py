#!/usr/bin/env python
# ============================================================
# nova/main.py - Nova Personal Assistant entry point
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import MIC_TIMEOUT, WAKE_WORD, MIC_PHRASE_LIMIT
from router import route
from stt import calibrate, listen_once, wait_for_wake_word
from tts import speak

BANNER = r"""
 _   _  ___  _   _   ___
| \ | |/ _ \| | | | / _ \
|  \| | | | | | | || | | |
| |\  | |_| | |_| || |_| |
|_| \_|\___/ \___/  \___/

  Personal AI Assistant - Windows Edition
  Say "{wake}" to activate.
  Type 'quit' and press Enter to exit.
""".format(wake=WAKE_WORD.title())


def startup(source=None):
    print(BANNER)
    print("=" * 50)
    print("Initialising Nova ...")

    calibrate(source)
    
    speak(f"Nova is online. Say {WAKE_WORD} to give me a command.")
    print("=" * 50)


def handle_command(command: str):
    print(f"[Nova] You said: {command}")

    response = route(command)
    if response == "__EXIT__":
        speak("Goodbye! Nova is shutting down.")
        print("\nNova stopped. Goodbye!\n")
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
                print(f"[Nova] Immediate command detected: {command}")
            else:
                speak("Yes? I'm listening.")
                print("[Nova] Listening for your command ...")
                command = listen_once(source=source, timeout=MIC_TIMEOUT, phrase_limit=MIC_PHRASE_LIMIT)

            if not command:
                speak("I didn't catch that. Please try again.")
                continue

            handle_command(command)

        except KeyboardInterrupt:
            speak("Goodbye! Nova is shutting down.")
            print("\nNova stopped. Goodbye!\n")
            sys.exit(0)

        except Exception as e:
            print(f"[Nova] Unexpected error: {e}")
            speak("Something went wrong. I'm still here. Please try again.")


if __name__ == "__main__":
    
    startup()
    main_loop()
