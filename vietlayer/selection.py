"""Choose between Tesseract and VietOCR without depending on the UI."""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class TextDecision:
    text: str
    source: str
    needs_review: bool
    reason: str


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text).split())


def choose_text(
    tesseract_text: str,
    confidence: int,
    vietocr_text: str | None,
    region_type: str,
) -> TextDecision:
    """Keep conflicting digits visible for manual review."""
    if region_type not in {"line", "isolated"}:
        raise ValueError("Invalid OCR region type.")
    tesseract_text = unicodedata.normalize("NFC", tesseract_text.strip())
    if vietocr_text is None:
        return TextDecision(tesseract_text, "tesseract", True, "VietOCR không đọc được vùng này")
    vietocr_text = unicodedata.normalize("NFC", vietocr_text.strip())
    if not vietocr_text:
        return TextDecision(tesseract_text, "tesseract", bool(tesseract_text), "VietOCR trả chữ rỗng")
    if not tesseract_text:
        return TextDecision(vietocr_text, "vietocr", region_type == "isolated", "Vùng Tesseract bỏ sót")

    tesseract_numbers = re.findall(r"\d+", tesseract_text)
    vietocr_numbers = re.findall(r"\d+", vietocr_text)
    if tesseract_numbers != vietocr_numbers:
        return TextDecision(tesseract_text, "tesseract", True, "Tesseract và VietOCR đọc số khác nhau")

    similarity = difflib.SequenceMatcher(None, _normalize(tesseract_text), _normalize(vietocr_text)).ratio()
    if confidence >= 90 and similarity >= 0.85:
        return TextDecision(tesseract_text, "tesseract", False, "Tesseract tin cậy cao và hai bản đọc gần giống")
    return TextDecision(
        vietocr_text,
        "vietocr",
        similarity < 0.7,
        "Hai bản đọc khác nhau nhiều" if similarity < 0.7 else "VietOCR giữ dấu tiếng Việt",
    )


def choose_with_ai(
    local: TextDecision,
    tesseract_text: str,
    vietocr_text: str | None,
    ai_text: str | None,
    region_type: str,
    uncertain: bool = False,
) -> TextDecision:
    """Use AI as corroboration; keep conflicting numbers for human review."""
    if not ai_text or not ai_text.strip():
        return local
    ai_text = unicodedata.normalize("NFC", ai_text.strip())
    if re.findall(r"\d+", ai_text) != re.findall(r"\d+", local.text):
        return TextDecision(local.text, local.source, True, "AI đọc số khác kết quả cục bộ")
    for source, candidate in (("tesseract", tesseract_text), ("vietocr", vietocr_text)):
        if candidate and ai_text == unicodedata.normalize("NFC", candidate.strip()):
            return TextDecision(ai_text, source, uncertain or region_type == "isolated", "AI xác nhận bản đọc cục bộ")
    similarity = difflib.SequenceMatcher(None, _normalize(ai_text), _normalize(local.text)).ratio()
    if local.needs_review and similarity >= 0.8:
        return TextDecision(ai_text, "ai", True, "AI đề xuất bản đọc thứ ba; cần đối chiếu")
    return TextDecision(local.text, local.source, True, "AI đọc khác kết quả cục bộ; cần đối chiếu")
