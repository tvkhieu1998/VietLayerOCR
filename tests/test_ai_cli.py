"""Codex CLI image review and deterministic OCR arbitration."""

import json
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from vietlayer import selection
from vietlayer.selection import TextDecision


class AiDecisionTests(unittest.TestCase):
    def test_ai_agreement_selects_matching_local_candidate(self):
        self.assertTrue(hasattr(selection, "choose_with_ai"))
        local = TextDecision("Bí danh", "vietocr", True, "khác bản đọc")
        result = selection.choose_with_ai(local, "Bi danh", "Bí danh", "Bi danh", "line")
        self.assertEqual((result.text, result.source, result.needs_review), ("Bi danh", "tesseract", False))

    def test_ai_different_number_keeps_local_and_flags_review(self):
        self.assertTrue(hasattr(selection, "choose_with_ai"))
        local = TextDecision("Năm 2023", "tesseract", True, "khác số")
        result = selection.choose_with_ai(local, "Năm 2023", "Năm 2028", "Năm 2028", "line")
        self.assertEqual((result.text, result.source, result.needs_review), ("Năm 2023", "tesseract", True))

    def test_ai_third_reading_needs_manual_review(self):
        self.assertTrue(hasattr(selection, "choose_with_ai"))
        local = TextDecision("Nguyễn Văn An", "vietocr", True, "khác bản đọc")
        result = selection.choose_with_ai(local, "Nguyễn Văn Ân", "Nguyễn Văn An", "Nguyễn Văn Anh", "line")
        self.assertEqual((result.text, result.source, result.needs_review), ("Nguyễn Văn Anh", "ai", True))


class CodexCliTests(unittest.TestCase):
    def test_sends_real_crop_as_image_and_accepts_only_matching_ids(self):
        self.assertIsNotNone(importlib.util.find_spec("vietlayer.ai_cli"))
        from vietlayer.ai_cli import CodexCliProvider

        with tempfile.TemporaryDirectory() as folder:
            crop = Image.new("RGB", (120, 40), "white")

            def complete(command, **kwargs):
                self.assertIn("-i", command)
                image_path = Path(command[command.index("-i") + 1])
                with Image.open(image_path) as opened:
                    self.assertEqual(opened.size, (120, 40))
                self.assertIn("--output-schema", command)
                self.assertIn("--sandbox", command)
                self.assertIn("read-only", command)
                self.assertIn("l01", kwargs["input"])
                Path(command[command.index("-o") + 1]).write_text(
                    json.dumps({"regions": [{"id": "l01", "text": "Bí danh", "uncertain": False}]}),
                    encoding="utf-8",
                )
                return type("Completed", (), {"returncode": 0, "stderr": "", "stdout": ""})()

            with patch("vietlayer.ai_cli.subprocess.run", side_effect=complete):
                result = CodexCliProvider("codex").review([
                    {"id": "l01", "crop": crop, "tesseract": "Bi danh", "vietocr": "Bí danh"}
                ], timeout_seconds=30)
            self.assertEqual(result, {"l01": {"text": "Bí danh", "uncertain": False}})

    def test_rejects_unrequested_region_id(self):
        self.assertIsNotNone(importlib.util.find_spec("vietlayer.ai_cli"))
        from vietlayer.ai_cli import CodexCliProvider

        def complete(command, **kwargs):
            Path(command[command.index("-o") + 1]).write_text(
                json.dumps({"regions": [{"id": "other", "text": "Sai", "uncertain": False}]}),
                encoding="utf-8",
            )
            return type("Completed", (), {"returncode": 0, "stderr": "", "stdout": ""})()

        with patch("vietlayer.ai_cli.subprocess.run", side_effect=complete):
            with self.assertRaises(ValueError):
                CodexCliProvider("codex").review([
                    {"id": "l01", "crop": Image.new("RGB", (40, 40)), "tesseract": "A", "vietocr": "B"}
                ], timeout_seconds=30)


if __name__ == "__main__":
    unittest.main()
