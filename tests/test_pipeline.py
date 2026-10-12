"""Checks for OCR decisions and positional hOCR changes."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from vietlayer.page import process_page
from vietlayer.selection import choose_text


HOCR = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body>
<div class="ocr_page" id="page_1" title="bbox 0 0 300 100">
<div class="ocr_carea" title="bbox 10 10 180 40"><p class="ocr_par">
<span class="ocr_line" title="bbox 10 10 180 40">
<span class="ocrx_word" title="bbox 10 10 55 40; x_wconf 75">Năm</span>
<span class="ocrx_word" title="bbox 60 10 150 40; x_wconf 75">tài</span>
</span></p></div></div></body></html>"""


class PipelineTests(unittest.TestCase):
    def test_conflicting_numbers_keep_tesseract_and_request_review(self):
        decision = choose_text("Năm 2023", 75, "Năm 2028", "line")
        self.assertEqual(decision.text, "Năm 2023")
        self.assertTrue(decision.needs_review)

    def test_page_replaces_words_inside_original_box(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            image_path, hocr_path, text_path = (directory / name for name in ("page.png", "page.hocr", "page.txt"))
            Image.new("RGB", (300, 100), "white").save(image_path)
            hocr_path.write_text(HOCR, encoding="utf-8")
            region = {"bbox": (10, 10, 180, 40), "words": [], "source": "test"}

            def assign_test_region(image, image_path, words):
                region["words"] = words
                for word in words:
                    word["region"] = region
                return [region], []

            with patch("vietlayer.page.analyze_regions", side_effect=assign_test_region), \
                 patch("vietlayer.page.read_image", return_value={"text": "Năm tài", "min_log_probability": -0.1, "reached_token_limit": False}):
                report = process_page(image_path, hocr_path, text_path, 1)
            self.assertEqual(report["line_count"], 1)
            self.assertIn("Năm", text_path.read_text(encoding="utf-8"))
            self.assertIn("bbox 10 10 180 40", hocr_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
