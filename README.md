# VietLayerOCR

VietLayerOCR creates searchable PDF/A files and plain text from scanned Vietnamese documents. The current repository contains the **local OCR core and CLI**. A PySide6 desktop interface and optional AI provider connection are planned but are not included yet.

## Pipeline

1. OCRmyPDF renders each PDF page, handles rotation and deskew, and assembles the output PDF/A.
2. Tesseract reads a contrast-enhanced copy of the page and creates positioned hOCR words.
3. RapidOCR detects text regions on the original page at two image sizes.
4. VietOCR reads each region locally. The selection step compares its result with Tesseract, preserves conflicting numbers, and flags uncertain text for review.
5. The selected words are written back into hOCR at the detected positions before OCRmyPDF creates the searchable text layer. The CLI also extracts a TXT file.

The source page image stays visible in the PDF. Model inference runs on the local CPU. This version makes no AI API request.

## Requirements

- Python 3.12, Tesseract with Vietnamese language data, Ghostscript, and OCRmyPDF's platform dependencies.
- `pip install -r requirements.txt`
- `pip install --no-deps vietocr==0.3.13` (its dependency versions otherwise conflict with this project's pinned NumPy/OpenCV range).
- A VietOCR checkpoint: `python scripts/download_vietocr.py --model transformer`. The script verifies its SHA-256 before use. Model weights are ignored by Git.

Platform package installation differs across Windows, macOS, and Linux. Check that `ocrmypdf`, `tesseract`, and `gs` are available on `PATH` before running the CLI.

## Use

```bash
python cli.py input.pdf output.pdf
python cli.py scan.png output.pdf --export both --language vie
python cli.py input.pdf output.pdf --model-dir /path/to/vietocr
```

`--export pdf`, `--export txt`, and `--export both` choose the output. `--force-ocr` processes pages that already contain text. `--no-pdfa` produces a regular PDF. The Python API is `vietlayer.process_document(input_path, output_pdf_path, OcrConfig(...))` and returns `OcrResult` with output paths, counts, duration, and page reports.

## Development

```bash
python -m unittest discover -s tests -v
```

Source file names, functions, classes, variables, environment variables, and report keys use English. User-facing messages are Vietnamese. The `models/vietocr/*.yml` names follow VietOCR's upstream checkpoint format.
