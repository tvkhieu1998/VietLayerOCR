# Install and build VietLayerOCR

[Tiếng Việt](BUILD.md) · **English** · [Back to README](../README.en.md)

Run the commands below at the repository root. The app needs Python **3.12**, [uv](https://docs.astral.sh/uv/getting-started/installation/), and Tesseract with Vietnamese data (`vie`). The current PDF/A workflow uses Ghostscript. VietOCR model weights are downloaded separately during setup and are not stored in Git.

If you do not have the source yet:

```bash
git clone https://github.com/tvkhieu1998/VietLayerOCR.git
cd VietLayerOCR
```

On Windows, run these commands in PowerShell. Open a new terminal after installing system tools so that `PATH` is refreshed.

## Run from source

### macOS

Install [Homebrew](https://brew.sh/) and [uv](https://docs.astral.sh/uv/getting-started/installation/) first, then run:

```bash
brew install tesseract tesseract-lang ghostscript
tesseract --list-langs
gs --version
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
uv pip install --python .venv/bin/python --no-deps vietocr==0.3.13
.venv/bin/python scripts/download_vietocr.py --model transformer
.venv/bin/python desktop.py --check
.venv/bin/python desktop.py
```

The Tesseract language list must include `vie`. The model download script checks the SHA-256 hash before saving the checkpoint.

### Linux (Debian/Ubuntu)

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and the native packages:

```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-vie ghostscript libgl1 libglib2.0-0
tesseract --list-langs
gs --version
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
uv pip install --python .venv/bin/python --no-deps vietocr==0.3.13
.venv/bin/python scripts/download_vietocr.py --model transformer
.venv/bin/python desktop.py --check
.venv/bin/python desktop.py
```

Other distributions need equivalent packages. If Qt reports that the `xcb` plugin is missing, install the Qt/X11 libraries required by your distribution.

### Windows (PowerShell)

Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/). Install **64-bit Tesseract** with `vie` language data and **64-bit Ghostscript**. You can use `winget install -e --id tesseract-ocr.tesseract` for Tesseract; download Ghostscript from its [official release page](https://ghostscript.com/releases/gsdnld.html). If the Tesseract installer omits `vie`, add `vie.traineddata` from [Tesseract tessdata](https://github.com/tesseract-ocr/tessdata) to its `tessdata` folder.

Open a new PowerShell window and check:

```powershell
tesseract --list-langs
gswin64c --version
uv --version
```

If `gswin64c` is not found, add Ghostscript's `bin` folder to `PATH` and open PowerShell again. At the repository root, run:

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
uv pip install --python .venv\Scripts\python.exe --no-deps vietocr==0.3.13
.\.venv\Scripts\python.exe scripts\download_vietocr.py --model transformer
.\.venv\Scripts\python.exe desktop.py --check
.\.venv\Scripts\python.exe desktop.py
```

On all three platforms, `--check` checks Python and PySide6 only; it does not run OCR. After the window opens, import a short scanned image or PDF to check the PDF and TXT flow. To use the CLI, run `.venv/bin/python cli.py input.pdf output.pdf --export both` (Windows: `.\.venv\Scripts\python.exe`).

## Package the desktop app

Build on the **target operating system and CPU architecture** after completing “Run from source.” The build script packages the VietOCR checkpoint, Python, and the app libraries. Users of the package still need Tesseract and `vie`; Linux and Windows users also need Ghostscript.

### macOS

```bash
uv pip install --python .venv/bin/python -r requirements-build.txt
.venv/bin/python scripts/build_desktop.py
open dist/VietLayerOCR.app
```

Output: `dist/VietLayerOCR.app`. Ghostscript is bundled only if `.venv/ghostscript/bin/gs` exists; with the Homebrew steps above, it remains a prerequisite on the target machine. PyInstaller signs this build locally. It is **not** Developer ID signed or notarized. The local test build was for Intel; build on Apple Silicon for a native release on that architecture.

### Linux

```bash
uv pip install --python .venv/bin/python -r requirements-build.txt
.venv/bin/python scripts/build_desktop.py
./dist/VietLayerOCR/VietLayerOCR
```

Output: the complete `dist/VietLayerOCR/` directory. Keep the directory intact when copying it to another machine, and install Tesseract/`vie` and Ghostscript there. Test the package on the Linux distributions you intend to support.

### Windows ZIP

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements-build.txt
.\.venv\Scripts\python.exe scripts\build_desktop.py
.\dist\VietLayerOCR\VietLayerOCR.exe
```

Output: `dist\VietLayerOCR\` and `dist\VietLayerOCR-windows.zip`. Extract the **entire ZIP** before launching `VietLayerOCR.exe`; do not launch it from inside a ZIP viewer. The target machine needs Tesseract/`vie` and Ghostscript.

The packaged app runs OCRmyPDF through its own worker, so a separate Python or `ocrmypdf` installation is not needed on the target machine. Codex/Claude CLI is optional and must be installed and signed in separately. The package can be large because it includes PyTorch, ONNX Runtime, and the VietOCR checkpoint.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `No module named PySide6` | Use `.venv/bin/python` or `.\.venv\Scripts\python.exe`; reinstall `requirements.txt` in that environment. |
| VietOCR model missing | Run `scripts/download_vietocr.py --model transformer` again; check `models/vietocr/vgg_transformer.pth`. |
| No `vie` language | Run `tesseract --list-langs`; install Vietnamese data for the Tesseract executable actually being used. |
| Ghostscript not found | Run `gs --version` (macOS/Linux) or `gswin64c --version` (Windows), check `PATH`, then open a new terminal. |
| Digitally signed PDF rejected | OCR changes a PDF and invalidates its digital signature. Use the original scan/image or an unsigned copy if OCR is needed. |
| Build reports missing icon/model | Run from the repository root and check `assets/app_icon.png` and the downloaded model. |

**Verification status:** The macOS build and local OCR flow have been smoke tested. Linux and Windows need real-machine testing before publishing downloadable packages.
