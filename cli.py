"""Command line entry point for VietLayerOCR."""

from __future__ import annotations

import argparse
from pathlib import Path

from vietlayer.core import OcrConfig, process_document


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo PDF có lớp chữ và/hoặc TXT từ PDF scan, ảnh")
    parser.add_argument("input", type=Path, help="PDF, PNG, JPG hoặc TIFF đầu vào")
    parser.add_argument("output", type=Path, help="Đường dẫn PDF đầu ra; dùng làm tên gốc khi chỉ xuất TXT")
    parser.add_argument("--export", choices=("pdf", "txt", "both"), default="both")
    parser.add_argument("--language", choices=("vie", "eng", "vie+eng"), default="vie")
    parser.add_argument("--model", choices=("transformer", "seq2seq"), default="transformer")
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--force-ocr", action="store_true", help="OCR lại cả trang đã có chữ")
    parser.add_argument("--no-pdfa", action="store_true", help="Xuất PDF thường")
    arguments = parser.parse_args()
    config = OcrConfig(
        language=arguments.language,
        page_mode="force" if arguments.force_ocr else "skip",
        model=arguments.model,
        model_dir=arguments.model_dir,
        pdfa=not arguments.no_pdfa,
        export_format=arguments.export,
    )
    result = process_document(arguments.input, arguments.output, config, print)
    for path in (result.pdf_path, result.text_path):
        if path is not None:
            print(path)
    print(f"{result.page_count} trang, {result.character_count} ký tự, {result.elapsed_seconds:.2f} giây")


if __name__ == "__main__":
    main()
