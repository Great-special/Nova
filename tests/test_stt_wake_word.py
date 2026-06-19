import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import stt


class WakeWordTests(unittest.TestCase):
    def test_calibrate_opens_microphone_when_source_is_not_supplied(self):
        class FakeMicrophone:
            def __enter__(self):
                return "mic source"

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeRecognizer:
            dynamic_energy_threshold = False

            def __init__(self):
                self.adjusted = None

            def adjust_for_ambient_noise(self, source, duration):
                self.adjusted = (source, duration)

        recognizer = FakeRecognizer()

        with patch.object(stt, "_microphone", FakeMicrophone()):
            with patch.object(stt, "_recognizer", recognizer):
                stt.calibrate()

        self.assertEqual(recognizer.adjusted, ("mic source", stt.AMBIENT_DURATION))
        self.assertTrue(recognizer.dynamic_energy_threshold)

    def test_extract_command_after_wake_word(self):
        self.assertEqual(
            stt.extract_wake_command("nova open chrome", "nova"),
            "open chrome",
        )

    def test_extract_empty_command_when_only_wake_word(self):
        self.assertEqual(stt.extract_wake_command("hey nova", "nova"), "")

    def test_extract_none_when_wake_word_missing(self):
        self.assertIsNone(stt.extract_wake_command("open chrome", "nova"))

    def test_wait_for_wake_word_returns_immediate_command(self):
        heard = iter(["background noise", "nova open chrome"])

        with patch.object(stt, "listen_once", side_effect=lambda *args, **kwargs: next(heard)):
            self.assertEqual(stt.wait_for_wake_word(), "open chrome")


if __name__ == "__main__":
    unittest.main()
