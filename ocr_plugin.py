"""OCRmyPDF hook: enhance the OCR image and revise positioned hOCR text."""

import logging
import os
import re
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
        try:
            report = process_page(original_image, Path(output_hocr), output_text, page_number)
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
