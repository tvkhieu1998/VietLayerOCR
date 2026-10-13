"""Checks for OCR decisions and positional hOCR changes."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from vietlayer.core import OcrConfig, OcrError, _split_page_texts, process_document
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
    def test_core_passes_codex_cli_configuration_to_ocr_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "source.png"
            Image.new("RGB", (40, 40), "white").save(source)
            model_dir = folder / "model"
            model_dir.mkdir()
            for name in ("base.yml", "vgg-transformer.yml", "vgg_transformer.pth"):
                (model_dir / name).touch()
            failure = type("Result", (), {"returncode": 1, "stderr": "test stopped", "stdout": ""})()
            with patch("vietlayer.core.shutil.which", return_value="/bin/tool"), \
                 patch("vietlayer.core.subprocess.run", return_value=failure) as run:
                with self.assertRaises(OcrError):
                    process_document(source, folder / "output.pdf",
                                     OcrConfig(model_dir=model_dir, ai_provider="codex-cli",
                                               ai_timeout_seconds=45, evidence_dir=folder / "evidence"))
            environment = run.call_args.kwargs["env"]
            self.assertEqual(environment["VIETLAYER_AI_PROVIDER"], "codex-cli")
            self.assertEqual(environment["VIETLAYER_AI_TIMEOUT_SECONDS"], "45")
            self.assertEqual(Path(environment["VIETLAYER_EVIDENCE_DIR"]), (folder / "evidence").resolve())

    def test_signed_pdf_requires_explicit_signature_invalidation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "signed.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            model_dir = Path(directory) / "model"
            model_dir.mkdir()
            for name in ("base.yml", "vgg-transformer.yml", "vgg_transformer.pth"):
                (model_dir / name).touch()
            failure = type("Result", (), {
                "returncode": 2,
                "stderr": "DigitalSignatureError: Input PDF has a digital signature. OCR would alter the document, invalidating the signature.",
                "stdout": "",
            })()
            with patch("vietlayer.core.shutil.which", return_value="/bin/tool"), \
                 patch("vietlayer.core.subprocess.run", return_value=failure) as run:
                with self.assertRaisesRegex(OcrError, "chữ ký số"):
                    process_document(source, Path(directory) / "output.pdf", OcrConfig(model_dir=model_dir))
                self.assertNotIn("--invalidate-digital-signatures", run.call_args.args[0])
                with self.assertRaises(OcrError):
                    process_document(source, Path(directory) / "output.pdf",
                                     OcrConfig(model_dir=model_dir, invalidate_digital_signatures=True))
                self.assertIn("--invalidate-digital-signatures", run.call_args.args[0])

    def test_page_text_split_preserves_blank_middle_page(self):
        self.assertEqual(
            _split_page_texts("Trang đầu\f\fTrang cuối\f", 3),
            ["Trang đầu", "", "Trang cuối"],
        )

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

    def test_ai_review_changes_selected_source_before_hocr_is_written(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            image_path, hocr_path, text_path = (folder / name for name in ("page.png", "page.hocr", "page.txt"))
            Image.new("RGB", (300, 100), "white").save(image_path)
            hocr_path.write_text(HOCR, encoding="utf-8")
            region = {"bbox": (10, 10, 180, 40), "words": [], "source": "test"}

            def assign_region(image, image_path, words):
                region["words"] = words
                for word in words:
                    word["region"] = region
                return [region], []

            with patch("vietlayer.page.analyze_regions", side_effect=assign_region), \
                 patch("vietlayer.page.read_image", return_value={"text": "Nợ thuế", "min_log_probability": -0.1,
                                                                  "reached_token_limit": False}), \
                 patch("vietlayer.ai_cli.CodexCliProvider.review", return_value={
                     "l01": {"text": "Năm tài", "uncertain": False}
                 }) as review:
                report = process_page(image_path, hocr_path, text_path, 1, ai_provider="codex-cli",
                                      evidence_dir=folder / "evidence")
            self.assertEqual(len(review.call_args.args[0]), 1)
            self.assertEqual(report["regions"][0]["source"], "tesseract")
            self.assertEqual(report["regions"][0]["candidates"]["ai"], "Năm tài")
            self.assertIn("Năm tài", text_path.read_text(encoding="utf-8"))
            self.assertTrue((folder / "evidence" / "page-00001" / "crop-l01.png").is_file())

    def test_ai_reviews_small_local_difference_even_without_review_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            image_path, hocr_path, text_path = (folder / name for name in ("page.png", "page.hocr", "page.txt"))
            Image.new("RGB", (300, 100), "white").save(image_path)
            hocr_path.write_text(HOCR, encoding="utf-8")
            region = {"bbox": (10, 10, 180, 40), "words": [], "source": "test"}

            def assign_region(image, image_path, words):
                region["words"] = words
                for word in words:
                    word["region"] = region
                return [region], []

            with patch("vietlayer.page.analyze_regions", side_effect=assign_region), \
                 patch("vietlayer.page.read_image", return_value={"text": "Năm Tài", "min_log_probability": -0.1,
                                                                  "reached_token_limit": False}), \
                 patch("vietlayer.ai_cli.CodexCliProvider.review", return_value={
                     "l01": {"text": "Năm tài", "uncertain": False}
                 }) as review:
                report = process_page(image_path, hocr_path, text_path, 1, ai_provider="codex-cli")
            review.assert_called_once()
            self.assertEqual(report["ai_review"]["requested"], 1)
            self.assertEqual(report["regions"][0]["source"], "tesseract")

    def test_manual_correction_updates_hocr_and_report(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            image_path = directory / "page.png"
            hocr_path = directory / "page.hocr"
            text_path = directory / "page.txt"
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
                report = process_page(image_path, hocr_path, text_path, 1, {"l01": "Năm tài chính"})
            self.assertIn("Năm tài chính", text_path.read_text(encoding="utf-8"))
            self.assertEqual(report["review_regions"][0]["source"], "manual")
            self.assertEqual(report["review_regions"][0]["bbox"], [10, 10, 180, 40])
            self.assertEqual(report["image_size"], [300, 100])

    def test_manual_correction_matches_bbox_when_region_number_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            image_path = directory / "page.png"
            hocr_path = directory / "page.hocr"
            text_path = directory / "page.txt"
            Image.new("RGB", (300, 100), "white").save(image_path)
            hocr_path.write_text(HOCR, encoding="utf-8")
            region = {"bbox": (10, 10, 180, 40), "words": [], "source": "test"}

            def assign_test_region(image, image_path, words):
                region["words"] = words
                for word in words:
                    word["region"] = region
                return [region], []

            corrections = {"l99": {"text": "Năm tài chính", "bbox": [10, 10, 180, 40]}}
            with patch("vietlayer.page.analyze_regions", side_effect=assign_test_region), \
                 patch("vietlayer.page.read_image", return_value={"text": "Năm tài", "min_log_probability": -0.1, "reached_token_limit": False}):
                report = process_page(image_path, hocr_path, text_path, 1, corrections)
            self.assertIn("Năm tài chính", text_path.read_text(encoding="utf-8"))
            self.assertEqual(report["review_regions"][0]["source"], "manual")
            self.assertEqual(report["unapplied_corrections"], [])

    def test_manual_correction_does_not_apply_to_wrong_bbox(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            image_path = directory / "page.png"
            hocr_path = directory / "page.hocr"
            Image.new("RGB", (300, 100), "white").save(image_path)
            hocr_path.write_text(HOCR, encoding="utf-8")
            region = {"bbox": (10, 10, 180, 40), "words": [], "source": "test"}

            def assign_test_region(image, image_path, words):
                region["words"] = words
                for word in words:
                    word["region"] = region
                return [region], []

            corrections = {"l01": {"text": "SAI VÙNG", "bbox": [220, 60, 270, 80]}}
            with patch("vietlayer.page.analyze_regions", side_effect=assign_test_region), \
                 patch("vietlayer.page.read_image", return_value={"text": "Năm tài", "min_log_probability": -0.1, "reached_token_limit": False}):
                report = process_page(image_path, hocr_path, None, 1, corrections)
            self.assertNotIn("SAI VÙNG", hocr_path.read_text(encoding="utf-8"))
            self.assertEqual(report["unapplied_corrections"], ["l01"])


if __name__ == "__main__":
    unittest.main()
