import tempfile
import unittest
from pathlib import Path

from app.briefing.prompt_loader import PromptUnavailable, load_briefing_prompt


class BriefingPromptLoaderTests(unittest.TestCase):
    def test_default_prompt_is_nonempty(self):
        self.assertTrue(load_briefing_prompt().strip())

    def test_missing_prompt_raises_safe_configuration_error(self):
        with tempfile.TemporaryDirectory() as scratch:
            missing = Path(scratch) / "missing.md"
            with self.assertRaises(PromptUnavailable) as raised:
                load_briefing_prompt(missing)
            self.assertNotIn(scratch, str(raised.exception))
            self.assertNotIn(str(missing), str(raised.exception))

    def test_empty_prompt_raises_safe_configuration_error(self):
        with tempfile.TemporaryDirectory() as scratch:
            empty = Path(scratch) / "empty.md"
            empty.write_text(" \n\t", encoding="utf-8")
            with self.assertRaises(PromptUnavailable) as raised:
                load_briefing_prompt(empty)
            self.assertNotIn(scratch, str(raised.exception))
            self.assertNotIn(str(empty), str(raised.exception))

    def test_each_call_reads_updated_file(self):
        with tempfile.TemporaryDirectory() as scratch:
            prompt = Path(scratch) / "briefing.md"
            prompt.write_text("primeira versão", encoding="utf-8")
            self.assertEqual(load_briefing_prompt(prompt), "primeira versão")
            prompt.write_text("segunda versão", encoding="utf-8")
            self.assertEqual(load_briefing_prompt(prompt), "segunda versão")


if __name__ == "__main__":
    unittest.main()
