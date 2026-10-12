"""Replace Tesseract hOCR words with positioned VietOCR text where useful."""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
import unicodedata
from pathlib import Path

from lxml import etree
from PIL import Image, ImageDraw, ImageOps

from .regions import analyze_regions, intersection_area
from .selection import choose_text
from .vietocr_reader import read_image


LOGGER = logging.getLogger(__name__)
LINE_CLASSES = {"ocr_line", "ocr_header", "ocr_textfloat", "ocr_caption"}
BOX_PATTERN = re.compile(r"bbox (-?\d+) (-?\d+) (-?\d+) (-?\d+)")
CONFIDENCE_PATTERN = re.compile(r"x_wconf (\d+)")
UNEXPECTED_CHARACTERS = re.compile(r"[^\x20-\x7E\n\r\tÀ-ỹĐđ–—‘’“”…]", re.UNICODE)
LATEX_PATTERN = re.compile(r"\\(?:frac|sqrt|begin|end|text)\b|\$\$")


def _class_name(element) -> str:
    return element.get("class", "") if isinstance(element.tag, str) else ""


def _text(element) -> str:
    return "".join(element.itertext()).strip()


def _box(element) -> tuple[int, int, int, int]:
    match = BOX_PATTERN.search(element.get("title", ""))
    return tuple(map(int, match.groups()))


def _remove(element) -> None:
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def preprocess_for_tesseract(input_path: Path, output_path: Path) -> None:
    image = Image.open(input_path)
    enhanced = ImageOps.autocontrast(image.convert("L"), cutoff=1)
    dpi = image.info.get("dpi")
    enhanced.save(output_path, dpi=dpi) if dpi else enhanced.save(output_path)


def _sort_reading_order(words: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for word in sorted(words, key=lambda item: (item["bbox"][1] + item["bbox"][3]) / 2):
        center = (word["bbox"][1] + word["bbox"][3]) / 2
        if rows and rows[-1]["top"] <= center <= rows[-1]["bottom"]:
            rows[-1]["words"].append(word)
        else:
            rows.append({"top": word["bbox"][1], "bottom": word["bbox"][3], "words": [word]})
    return [word for row in rows for word in sorted(row["words"], key=lambda item: item["bbox"][0])]


def _crop_line(image: Image.Image, region: dict, words: list[dict], isolated: list[dict]) -> Image.Image:
    box = region["bbox"]
    expanded = (max(0, box[0] - 6), max(0, box[1] - 6),
                min(image.width, box[2] + 6), min(image.height, box[3] + 6))
    crop = image.crop(expanded)
    draw = ImageDraw.Draw(crop)
    covered = [word["bbox"] for word in words if word["region"] is not region and word["region"] is not None]
    covered += [item["bbox"] for item in isolated]
    for other_box in covered:
        if intersection_area(other_box, expanded):
            draw.rectangle((other_box[0] - expanded[0] - 1, other_box[1] - expanded[1] - 1,
                            other_box[2] - expanded[0] + 1, other_box[3] - expanded[1] + 1), fill="white")
    for word in region["words"]:
        word_box = word["bbox"]
        ascent = int(0.35 * (word_box[3] - word_box[1]))
        word_box = (max(word_box[0], expanded[0]), max(word_box[1] - ascent, expanded[1]),
                    min(word_box[2], expanded[2]), min(word_box[3], expanded[3]))
        if word_box[2] > word_box[0] and word_box[3] > word_box[1]:
            crop.paste(image.crop(word_box), (word_box[0] - expanded[0], word_box[1] - expanded[1]))
    if crop.height < 64:
        scale = 64 / crop.height
        crop = crop.resize((round(crop.width * scale), 64), Image.Resampling.LANCZOS)
    return crop


def _crop_isolated(image: Image.Image, region: dict) -> Image.Image:
    crop = image.crop(region["expanded_bbox"])
    if crop.height < 96:
        scale = 96 / crop.height
        crop = crop.resize((round(crop.width * scale), 96), Image.Resampling.LANCZOS)
    return crop


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(character for character in normalized if character.isalnum() and not unicodedata.combining(character))


def _validate_result(result: dict, previous_text: str | None) -> tuple[str | None, list[str]]:
    text = result["text"]
    if result.get("reached_token_limit"):
        return None, ["sinh lặp tới giới hạn token"]
    unexpected = sorted(set(UNEXPECTED_CHARACTERS.findall(text)))
    if unexpected or LATEX_PATTERN.search(text):
        return None, ["ký tự ngoài phạm vi tiếng Việt"]
    reasons = []
    probability = result.get("min_log_probability")
    if probability is not None and probability < -2.0:
        reasons.append("mô hình không chắc (logprob thấp)")
    if previous_text and text:
        similarity = difflib.SequenceMatcher(None, _normalize(previous_text), _normalize(text)).ratio()
        if similarity < 0.5:
            reasons.append(f"lệch nhiều so với Tesseract (giống {similarity:.0%})")
    return text, reasons


def _tighten_box(box, ink: Image.Image) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    if right - left < 2 or bottom - top < 4:
        return box
    crop = ink.crop(box)
    rows = [value * crop.width / 255 for value in crop.resize((1, crop.height), Image.Resampling.BOX).get_flattened_data()]
    peak = max(rows)
    if peak <= 0:
        return box
    dark = [value >= max(2, 0.2 * peak) for value in rows]
    groups, start, gap, last = [], None, 0, 0
    for index, is_dark in enumerate(dark + [False]):
        if is_dark:
            if start is None:
                start = index
            gap, last = 0, index
        elif start is not None:
            gap += 1
            if gap > max(1, 0.08 * len(rows)) or index == len(dark):
                groups.append((start, last + 1))
                start = None
    if not groups:
        return box
    first, last = max(groups, key=lambda group: sum(rows[group[0]:group[1]]))
    if last - first < 0.3 * (bottom - top) and last - first < 8:
        return box
    return left, top + first, right, top + last


def _split_overlaps(entries: list[tuple]) -> list[tuple]:
    entries = [list(entry) for entry in entries]
    for first_index in range(len(entries)):
        for second_index in range(len(entries)):
            if first_index == second_index:
                continue
            first, second = entries[first_index][0], entries[second_index][0]
            if first[1] <= second[1] < first[3] < second[3] and min(first[2], second[2]) > max(first[0], second[0]):
                middle = (second[1] + first[3]) // 2
                entries[first_index][0] = (first[0], first[1], first[2], max(first[1] + 2, middle))
                entries[second_index][0] = (second[0], min(second[3] - 2, middle), second[2], second[3])
    return [tuple(entry) for entry in entries]


def _word_boxes(box, words: list[str]) -> list[tuple[int, int, int, int]]:
    left, top, right, bottom = box
    total = sum(len(word) + 1 for word in words) or 1
    result, cursor = [], float(left)
    for word in words:
        width = (right - left) * (len(word) + 1) / total
        word_right = cursor + width * len(word) / (len(word) + 1)
        result.append((round(cursor), top, max(round(cursor) + 1, round(word_right)), bottom))
        cursor += width
    return result


def _insert_line(page_element, box, identifier: str, text: str) -> None:
    namespace = page_element.tag.split("}")[0] + "}" if page_element.tag.startswith("{") else ""
    lines = [line.split() for line in re.split(r"[\n\r]+", text) if line.split()]
    if not lines:
        return
    left, top, right, bottom = box
    height = (bottom - top) / len(lines)
    for index, words in enumerate(lines):
        line_box = (left, round(top + index * height), right, round(top + (index + 1) * height))
        title = f"bbox {line_box[0]} {line_box[1]} {line_box[2]} {line_box[3]}"
        area = etree.SubElement(page_element, namespace + "div", {"class": "ocr_carea", "id": f"{identifier}_{index}", "title": title})
        paragraph = etree.SubElement(area, namespace + "p", {"class": "ocr_par", "id": f"{identifier}_{index}_p", "title": title})
        line = etree.SubElement(paragraph, namespace + "span", {
            "class": "ocr_line", "id": f"{identifier}_{index}_l",
            "title": f"{title}; baseline 0 0; x_size {line_box[3] - line_box[1]}; x_descenders 0; x_ascenders 0",
        })
        for word_index, (word, word_box) in enumerate(zip(words, _word_boxes(line_box, words))):
            element = etree.SubElement(line, namespace + "span", {
                "class": "ocrx_word", "id": f"{identifier}_{index}_w{word_index}",
                "title": f"bbox {word_box[0]} {word_box[1]} {word_box[2]} {word_box[3]}; x_wconf 90",
            })
            element.text = word
            element.tail = " "


def _page_text(tree) -> str:
    paragraphs = []
    for area in tree.iter():
        if _class_name(area) != "ocr_carea":
            continue
        lines = []
        for line in area.iter():
            if _class_name(line) in LINE_CLASSES:
                text = " ".join(_text(word) for word in line.iter() if _class_name(word) == "ocrx_word" and _text(word))
                if text:
                    lines.append(text)
        if lines:
            paragraphs.append("\n".join(lines))
    return "\n\n".join(paragraphs) + "\n"


def process_page(image_path: Path, hocr_path: Path, text_path: Path | None, page_number: int) -> dict:
    report = {"page": page_number, "review_regions": [], "printed_corrections": [], "errors": [],
              "isolated_region_count": 0, "line_count": 0}
    tree = etree.parse(str(hocr_path), etree.XMLParser(resolve_entities=False, no_network=True))
    page_element = next(element for element in tree.iter() if _class_name(element) == "ocr_page")
    image = Image.open(image_path).convert("RGB")
    words = []
    for line in [element for element in tree.iter() if _class_name(element) in LINE_CLASSES]:
        for element in line.iter():
            if _class_name(element) == "ocrx_word" and _text(element):
                match = CONFIDENCE_PATTERN.search(element.get("title", ""))
                words.append({"element": element, "text": _text(element), "bbox": _box(element),
                              "confidence": int(match.group(1)) if match else 0, "line": line})
    lines, isolated = analyze_regions(image, image_path, words)
    discarded = [word for word in words if word["region"] is None]
    for word in discarded:
        _remove(word["element"])
    report["discarded_words"] = [word["text"] for word in discarded]
    for region in lines:
        region["words"] = _sort_reading_order(region["words"])
    report["line_count"] = len(lines)
    report["isolated_region_count"] = len(isolated)
    entries = []
    source_counts = {}
    grouped = [(f"l{index:02d}", "line", region, region["bbox"], _crop_line(image, region, words, isolated))
               for index, region in enumerate(lines, 1)]
    grouped += [(f"i{index:02d}", "isolated", region, region["bbox"], _crop_isolated(image, region))
                for index, region in enumerate(isolated, 1)]
    for identifier, region_type, region, box, crop in grouped:
        previous = " ".join(word["text"] for word in region["words"])
        confidence = min((word["confidence"] for word in region["words"]), default=0)
        try:
            raw = read_image(crop, os.environ.get("VIETOCR_MODEL_NAME", "transformer"),
                             Path(os.environ.get("VIETOCR_MODEL_DIR", "models/vietocr")))
            candidate, model_reasons = _validate_result(raw, previous if region_type == "line" else None)
        except Exception as error:  # Preserve Tesseract text for a failed region.
            LOGGER.exception("VietOCR failed on page %s region %s", page_number, identifier)
            candidate, model_reasons = None, [f"VietOCR lỗi: {type(error).__name__}"]
            report["errors"].append(f"{identifier}: {type(error).__name__}")
        decision = choose_text(previous, confidence, candidate, region_type)
        source_counts[decision.source] = source_counts.get(decision.source, 0) + 1
        reasons = ([decision.reason] if decision.needs_review else []) + model_reasons
        if decision.source == "vietocr" and decision.text:
            for word in region["words"]:
                _remove(word["element"])
            entries.append((box, f"p{page_number}{identifier}", decision.text))
            if region_type == "line" and decision.text != previous:
                report["printed_corrections"].append({"page": page_number, "before": previous,
                    "after": decision.text, "source": "VietOCR",
                    "numbers_changed": re.findall(r"\d+", previous) != re.findall(r"\d+", decision.text)})
        if region_type == "isolated" or reasons:
            report["review_regions"].append({"page": page_number, "region": identifier,
                "text": decision.text, "needs_review": bool(reasons), "reasons": reasons,
                "source": decision.source,
                "candidates": {"tesseract": previous, "vietocr": candidate or ""}})
    report["local_reader"] = {"regions": len(grouped), "vietocr_calls": len(grouped), "sources": source_counts}
    ink = ImageOps.autocontrast(image.convert("L"), cutoff=1).point(lambda value: 255 if value < 140 else 0)
    entries = [(_tighten_box(box, ink) if "\n" not in text else box, identifier, text)
               for box, identifier, text in entries]
    for box, identifier, text in sorted(_split_overlaps(entries), key=lambda item: (item[0][1], item[0][0])):
        _insert_line(page_element, box, identifier, text)
    for element in [item for item in tree.iter() if _class_name(item) in LINE_CLASSES | {"ocr_par", "ocr_carea"}]:
        if not any(_class_name(word) == "ocrx_word" for word in element.iter()):
            _remove(element)
    tree.write(str(hocr_path), xml_declaration=True, encoding="UTF-8", doctype=tree.docinfo.doctype)
    if text_path is not None:
        Path(text_path).write_text(_page_text(tree), encoding="utf-8")
    return report


def save_page_report(report_dir: Path, report: dict) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / f"page_{report['page']:05d}.json").write_text(
        json.dumps(report, ensure_ascii=False), encoding="utf-8"
    )
