# VietLayerOCR

VietLayerOCR creates searchable PDF/A files and plain text from scanned Vietnamese documents. The repository contains a local OCR core, CLI, and a PySide6 desktop interface. The core can optionally ask a Codex or Claude CLI, or an OpenAI, Anthropic, or Gemini API, to review selected image crops.

## Pipeline

1. OCRmyPDF renders each PDF page, handles rotation and deskew, and assembles the output PDF/A.
2. Tesseract reads a contrast-enhanced copy of the page and creates positioned hOCR words.
3. RapidOCR detects text regions on the original page at two image sizes.
4. VietOCR reads each region locally. The selection step compares its result with Tesseract, preserves conflicting numbers, and flags uncertain text for review.
5. When enabled, the selected CLI or API reviews cropped regions where the local readers disagree or mark text uncertain. Its JSON response is checked against the requested region IDs. Conflicting numbers remain flagged for human review.
6. The selected words are written back into hOCR at the detected positions before OCRmyPDF creates the searchable text layer. The CLI also extracts a TXT file.

The source page image stays visible in the PDF. Tesseract and VietOCR run locally. The optional AI transport sends selected crops and both local readings to the configured provider.

## Requirements

- Python 3.12, Tesseract with Vietnamese language data, Ghostscript, and OCRmyPDF's platform dependencies.
- On macOS/Linux, create a project environment with `uv venv --python 3.12 .venv`, then install `uv pip install --python .venv/bin/python -r requirements.txt` and `uv pip install --python .venv/bin/python --no-deps vietocr==0.3.13`.
- On Windows, use `.venv\\Scripts\\python.exe` in the same `uv pip install --python` commands.
- A VietOCR checkpoint: `python scripts/download_vietocr.py --model transformer`. The script verifies its SHA-256 before use. Model weights are ignored by Git.

Platform package installation differs across Windows, macOS, and Linux. Check that `ocrmypdf`, `tesseract`, and `gs` are available on `PATH` before running the CLI.

## Use

Launch the desktop interface:

```bash
python desktop.py
python desktop.py --check
```

The launcher automatically uses the project's `.venv` when it exists. `--check` prints the Python and PySide6 versions without opening a window. OCR also needs `tesseract`, `gs`, and the `ocrmypdf` executable available on `PATH`; the launcher adds `.venv/bin` (or `.venv\\Scripts`) to `PATH`.

Use **Thêm tài liệu** to import a PDF or image, then **Nhận dạng tài liệu** in the left panel. The right panel has **Chi tiết** for reviewing a flagged region and **Tổng thể text** for reading and copying the selected page's text. In Chi tiết, choose **Chỉnh sửa** to unlock the selected text. After editing, **Lưu chỉnh sửa** reprocesses the original document with the correction before PDF/TXT export. Corrections carry region coordinates; if a region cannot be matched on the next pass, the app blocks export and asks for review. **Xuất TXT** in Tổng thể text uses the same whole-document export as the top bar; the page view itself is read-only. **Xuất PDF** saves the searchable PDF separately. OCR runs in a background thread so the window remains responsive.

The **Sử dụng AI** switch displays a privacy warning. **Cài đặt OCR** switches to an AI settings page inside the main window. Two radio controls select Provider CLI or API AI; Provider CLI is selected by default. The CLI column checks installation, authentication, and live connectivity without sending a document, then enables model and effort selection. The API column accepts an OpenAI, Anthropic, or Gemini key for the current app session. The key is held in memory and is not saved to QSettings. Both transports receive the same selected crop batches and return the same region JSON; the same arbitration rules select the final OCR text. A failed API batch falls back to the local OCR result and is reported in the desktop status. CLI preferences are saved locally, but the app requires a fresh successful connection check each session. With AI off, recognition uses only local Tesseract and VietOCR. The desktop uses the transformer model under `models/vietocr` by default, or the directory in `VIETLAYER_MODEL_DIR`.

The CLI remains available:

```bash
python cli.py input.pdf output.pdf
python cli.py scan.png output.pdf --export both --language vie
python cli.py input.pdf output.pdf --model-dir /path/to/vietocr
```

`--export pdf`, `--export txt`, and `--export both` choose the output. `--force-ocr` processes pages that already contain text. `--no-pdfa` produces a regular PDF. The Python API is `vietlayer.process_document(input_path, output_pdf_path, OcrConfig(...))` and returns `OcrResult` with output paths, counts, duration, and page reports.

To try the optional AI core with a Codex CLI that is already installed and signed in:

```python
from pathlib import Path
from vietlayer import OcrConfig, process_document

result = process_document(
    "scan.png",
    "output.pdf",
    OcrConfig(ai_provider="codex-cli", evidence_dir=Path("evidence")),
)
```

Only enable this for documents whose selected text crops may be sent to the provider. If the AI call fails, the page keeps its local OCR choice and the desktop reports the failed AI batches. A synthetic end-to-end Codex run and stage evidence are in [the AI core report](reports/ai-core-review.html).

## Development

```bash
python -m unittest discover -s tests -v
```

Source file names, functions, classes, variables, environment variables, and report keys use English. User-facing messages are Vietnamese. The `models/vietocr/*.yml` names follow VietOCR's upstream checkpoint format.

**Current review limitation:** Highlight boxes use OCR page pixel coordinates mapped to the displayed PDF page. OCRmyPDF may rotate or deskew a source page, so overlays should be checked visually on heavily transformed scans. Saving a manual correction reruns OCR to keep the PDF/A text layer and TXT consistent; it takes approximately as long as the first pass.
