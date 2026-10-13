# VietLayerOCR

[Tiếng Việt](README.md) · **English**

VietLayerOCR is a desktop app for recognizing scanned Vietnamese documents. It creates searchable, copyable PDF/A files and exports plain text. Its local OCR pipeline uses OCRmyPDF, Tesseract, RapidOCR, and VietOCR. Optional AI can review text regions that the local readers disagree on.

![VietLayerOCR icon](assets/app_icon.png)

## Get started

You can [run from source](docs/BUILD.en.md#run-from-source) or [build a desktop app](docs/BUILD.en.md#package-the-desktop-app) on macOS, Linux, and Windows. The build guide covers native dependencies, verification commands, and output locations.

For a quick source install on macOS, first install [Homebrew](https://brew.sh/) and [uv](https://docs.astral.sh/uv/getting-started/installation/), then run these commands at the repository root:

```bash
brew install tesseract tesseract-lang ghostscript
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
uv pip install --python .venv/bin/python --no-deps vietocr==0.3.13
.venv/bin/python scripts/download_vietocr.py --model transformer
.venv/bin/python desktop.py --check
.venv/bin/python desktop.py
```

If you do not have the repository yet, run `git clone https://github.com/tvkhieu1998/VietLayerOCR.git` and `cd VietLayerOCR` first. Check that `tesseract --list-langs` includes `vie`. See the full [Linux](docs/BUILD.en.md#linux-debianubuntu) and [Windows](docs/BUILD.en.md#windows-powershell) instructions in the build guide.

> **Build status:** The macOS app has been built and smoke tested locally. The Linux and Windows build commands are prepared but have not yet been verified on those systems. The current macOS `.app` is not Developer ID signed or notarized.

## Use the app

1. Select **Thêm tài liệu** to import a PDF or image.
2. Select **Nhận dạng tài liệu**. OCR runs locally by default; no AI account is needed.
3. Use **Chi tiết** to review and edit a flagged region. Use **Tổng thể text** to read and copy the selected page's text.
4. Select **Xuất PDF** for a searchable PDF or **Xuất TXT** for plain text. Check the results against the original scan before using them.

For optional AI review, open **Cài đặt OCR**, choose Provider CLI or API AI, and check the connection. When **Sử dụng AI** is on, selected image crops and local OCR readings may be sent to the configured provider. API keys are held in memory for the current session and are not saved to QSettings. Failed AI calls leave the local OCR result in place and appear in the app status.

## Pipeline

1. OCRmyPDF prepares each page, handles rotation and deskew, and produces the PDF/A file.
2. Tesseract reads a contrast-enhanced page and creates positioned hOCR text.
3. RapidOCR finds text regions; VietOCR reads each region again.
4. The selection step compares both readings and flags conflicting numbers for review. AI can optionally review uncertain regions.
5. Selected text is placed into the PDF text layer at the detected positions. The app also exports TXT.

## CLI and development

After [installing the source environment](docs/BUILD.en.md#run-from-source):

```bash
.venv/bin/python cli.py input.pdf output.pdf --export both --language vie
.venv/bin/python -m unittest discover -s tests -v
```

On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python.exe`. CLI options include `--export pdf|txt|both`, `--force-ocr` for PDFs that already contain text, and `--no-pdfa` for a regular PDF. The Python API is `vietlayer.process_document(input_path, output_pdf_path, OcrConfig(...))`. The [AI core report](reports/ai-core-review.html) contains stage evidence from an end-to-end run.

## Current limitations

- Tesseract and Vietnamese language data must be installed on the machine running the app. Linux and Windows also need Ghostscript. The macOS build bundles Ghostscript only when `.venv/ghostscript/bin/gs` exists at build time.
- Highlight boxes map OCR image coordinates onto the displayed PDF page. Check them visually on scans with substantial rotation or deskew.
- Saving a manual correction reruns OCR to keep PDF and TXT consistent; this takes about as long as the first pass.
- Builds can be large because they include PyTorch, ONNX Runtime, and the VietOCR checkpoint. Codex/Claude CLI tools, when used, must be installed separately.

Source file names, functions, and variables use English. The app's user-facing copy is Vietnamese.

## License

The project's own source code is released under the [MIT License](LICENSE). This repository currently provides source code and self-build instructions; it does not publish a prebuilt app. PySide6, Ghostscript, VietOCR, and other third-party components retain their own licenses. Anyone redistributing a packaged app must review and comply with the licenses of the components included in that package.
