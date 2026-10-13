"""OCRmyPDF hook: enhance the OCR image and revise positioned hOCR text."""

import logging
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ocrmypdf import hookimpl  # noqa: E402
from ocrmypdf.builtin_plugins.tesseract_ocr import TesseractOcrEngine  # noqa: E402

from vietlayer.page import preprocess_for_tesseract, process_page, save_page_report  # noqa: E402


LOGGER = logging.getLogger(__name__)


class LocalOcrEngine(TesseractOcrEngine):
    @staticmethod
    def generate_hocr(input_file, output_hocr, output_text, options):
        original_image = Path(input_file)
        enhanced_image = original_image.with_name(original_image.stem + "_enhanced.png")
        try:
            preprocess_for_tesseract(original_image, enhanced_image)
        except Exception:
            LOGGER.exception("Could not enhance the OCR image; using the original")
            enhanced_image = original_image
        TesseractOcrEngine.generate_hocr(enhanced_image, output_hocr, output_text, options)
        if os.environ.get("VIETLAYER_ENABLE") != "1":
            return
        match = re.match(r"(\d+)", original_image.name)
        page_number = int(match.group(1)) if match else 0
        evidence_dir = os.environ.get("VIETLAYER_EVIDENCE_DIR")
        if evidence_dir and enhanced_image.is_file():
            page_dir = Path(evidence_dir) / f"page-{page_number:05d}"
            page_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(enhanced_image, page_dir / "tesseract-enhanced.png")
        try:
            correction_path = os.environ.get("VIETLAYER_CORRECTIONS_PATH")
            corrections = {}
            if correction_path:
                corrections = json.loads(Path(correction_path).read_text(encoding="utf-8")).get(str(page_number), {})
            report = process_page(
                original_image, Path(output_hocr), output_text, page_number, corrections,
                ai_provider=os.environ.get("VIETLAYER_AI_PROVIDER"),
                ai_model=os.environ.get("VIETLAYER_AI_MODEL"),
                ai_effort=os.environ.get("VIETLAYER_AI_EFFORT"),
                ai_api_key=os.environ.get("VIETLAYER_AI_API_KEY"),
                ai_timeout_seconds=int(os.environ.get("VIETLAYER_AI_TIMEOUT_SECONDS", "180")),
                evidence_dir=Path(evidence_dir) if evidence_dir else None,
            )
        except Exception as error:
            LOGGER.exception("Page %s: OCR revision failed; preserving Tesseract text", page_number)
            report = {"page": page_number, "review_regions": [], "printed_corrections": [],
                      "isolated_region_count": 0, "line_count": 0,
                      "errors": [f"VietOCR lỗi ({type(error).__name__}); giữ chữ Tesseract"]}
        report_dir = os.environ.get("VIETLAYER_REPORT_DIR")
        if report_dir:
            save_page_report(Path(report_dir), report)


@hookimpl
def get_ocr_engine():
    return LocalOcrEngine()
