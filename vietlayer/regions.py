"""Locate text regions with RapidOCR and associate Tesseract words."""

from __future__ import annotations

import io
import re
import unicodedata

from PIL import Image


_detector = None
DETECTION_WIDTHS = (1100, 1600)
MERGE_OVERLAP = 0.6
_SYLLABLE = re.compile(r"^(ngh|ng|gh|gi|kh|nh|ph|qu|th|tr|ch|[bcdđghklmnpqrstvx])?[aăâeêioôơuưy]{1,3}(ng|nh|ch|[cmnptiouy])?$")


def _get_detector():
    global _detector
    if _detector is None:
        from rapidocr import RapidOCR

        _detector = RapidOCR()
    return _detector


def intersection_area(first, second) -> int:
    return max(0, min(first[2], second[2]) - max(first[0], second[0])) * max(
        0, min(first[3], second[3]) - max(first[1], second[1])
    )


def box_area(box) -> int:
    return max(1, (box[2] - box[0]) * (box[3] - box[1]))


def _valid_syllable(text: str) -> bool:
    text = text.strip(".,;:!?()[]{}\"'“”‘’–-…").lower()
    if not text or any(character.isdigit() for character in text):
        return False
    normalized = unicodedata.normalize("NFD", text)
    normalized = "".join(character for character in normalized if unicodedata.category(character) != "Mn")
    return bool(_SYLLABLE.fullmatch(unicodedata.normalize("NFC", normalized)))


def _good_word(word: dict) -> bool:
    return word["confidence"] >= 60 and (
        _valid_syllable(word["text"])
        or (word["confidence"] >= 80 and bool(re.search(r"\d", word["text"])))
    )


def _detect_at_width(image: Image.Image, width: int) -> list[tuple[int, int, int, int]]:
    scale = min(1.0, width / image.width)
    small = image if scale == 1.0 else image.resize(
        (round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS
    )
    buffer = io.BytesIO()
    small.convert("RGB").save(buffer, "PNG")
    result = _get_detector()(buffer.getvalue(), use_det=True, use_cls=False, use_rec=False)
    boxes = []
    for polygon in (result.boxes if result.boxes is not None else []):
        x_values = [float(point[0]) / scale for point in polygon]
        y_values = [float(point[1]) / scale for point in polygon]
        box = (
            max(0, int(min(x_values))), max(0, int(min(y_values))),
            min(image.width, int(max(x_values)) + 1),
            min(image.height, int(max(y_values)) + 1),
        )
        if box[2] > box[0] and box[3] > box[1]:
            boxes.append(box)
    return boxes


def _same_line(first, second) -> bool:
    overlap = min(first[3], second[3]) - max(first[1], second[1])
    return overlap >= 0.5 * (first[3] - first[1]) and overlap >= 0.5 * (second[3] - second[1])


def _merge_regions(regions: list[dict]) -> list[dict]:
    regions = list(regions)
    changed = True
    while changed:
        changed = False
        for first_index in range(len(regions)):
            for second_index in range(first_index + 1, len(regions)):
                first, second = regions[first_index]["bbox"], regions[second_index]["bbox"]
                if _same_line(first, second) and intersection_area(first, second) >= MERGE_OVERLAP * min(box_area(first), box_area(second)):
                    source = regions[first_index]["source"] if regions[first_index]["source"] == regions[second_index]["source"] else "merged"
                    regions[first_index] = {
                        "bbox": (min(first[0], second[0]), min(first[1], second[1]), max(first[2], second[2]), max(first[3], second[3])),
                        "words": [], "supplemented": False, "source": source,
                    }
                    del regions[second_index]
                    changed = True
                    break
            if changed:
                break
    return regions


def _assign_words(words: list[dict], regions: list[dict]) -> None:
    for word in words:
        candidates = [region for region in regions if intersection_area(word["bbox"], region["bbox"]) / box_area(word["bbox"]) >= 0.5]
        if candidates:
            center = (word["bbox"][1] + word["bbox"][3]) / 2
            region = min(candidates, key=lambda item: abs((item["bbox"][1] + item["bbox"][3]) / 2 - center))
            word["region"] = region
            region["words"].append(word)


def _supplement_regions(words: list[dict], regions: list[dict]) -> None:
    by_line: dict[int, list[dict]] = {}
    for word in words:
        by_line.setdefault(id(word["line"]), []).append(word)
    for line_words in by_line.values():
        groups: list[list[dict] | None] = []
        for word in sorted(line_words, key=lambda item: item["bbox"][0]):
            height = word["bbox"][3] - word["bbox"][1]
            if word["region"] is None and groups and groups[-1] and word["bbox"][0] - groups[-1][-1]["bbox"][2] <= 2 * max(height, 10):
                groups[-1].append(word)
            elif word["region"] is None:
                groups.append([word])
            else:
                groups.append(None)
        for group in (group for group in groups if group):
            good_count = sum(_good_word(word) for word in group)
            if good_count < 2 or good_count < 0.5 * len(group):
                continue
            region = {
                "bbox": (min(word["bbox"][0] for word in group), min(word["bbox"][1] for word in group),
                         max(word["bbox"][2] for word in group), max(word["bbox"][3] for word in group)),
                "words": list(group), "supplemented": True, "source": "tesseract",
            }
            for word in group:
                word["region"] = region
            regions.append(region)


def _expand_isolated(regions: list[dict], width: int, height: int) -> None:
    for region in regions:
        left, top, right, bottom = region["bbox"]
        line_height = bottom - top
        expanded = [max(0, left - line_height // 2), max(0, top - line_height // 3),
                    min(width, right + line_height // 2), min(height, bottom + line_height // 3)]
        for other in regions:
            if other is region:
                continue
            other_box = other["bbox"]
            if other_box[2] <= expanded[0] or other_box[0] >= expanded[2]:
                continue
            if other_box[3] <= top:
                expanded[1] = max(expanded[1], other_box[3])
            elif other_box[1] >= bottom:
                expanded[3] = min(expanded[3], other_box[1])
        region["expanded_bbox"] = tuple(expanded)


def analyze_regions(image: Image.Image, image_path, words: list[dict]) -> tuple[list[dict], list[dict]]:
    for word in words:
        word["region"] = None
    regions = _merge_regions([
        {"bbox": box, "words": [], "supplemented": False, "source": str(width)}
        for width in DETECTION_WIDTHS for box in _detect_at_width(image, width)
    ])
    _assign_words(words, regions)
    _supplement_regions(words, regions)
    lines, isolated = [], []
    for region in regions:
        if any(_good_word(word) for word in region["words"]):
            lines.append(region)
        else:
            isolated.append({"bbox": region["bbox"], "words": list(region["words"]), "source_region": region})
    lines.sort(key=lambda region: (region["bbox"][1], region["bbox"][0]))
    isolated.sort(key=lambda region: (region["bbox"][1] // 20, region["bbox"][0]))
    _expand_isolated(isolated, image.width, image.height)
    return lines, isolated
