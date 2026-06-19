import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import router


class RouterTests(unittest.TestCase):
    def test_play_song_on_youtube_keeps_query_before_youtube(self):
        with patch("skills.play_youtube", return_value="ok") as play_youtube:
            self.assertEqual(router.route("play afrobeats on youtube"), "ok")

        play_youtube.assert_called_once_with("afrobeats")

    def test_search_youtube_for_query_keeps_query_after_trigger(self):
        with patch("skills.play_youtube", return_value="ok") as play_youtube:
            self.assertEqual(router.route("search youtube for python tutorials"), "ok")

        play_youtube.assert_called_once_with("python tutorials")


if __name__ == "__main__":
    unittest.main()
