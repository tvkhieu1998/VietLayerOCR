# Cài và tự build VietLayerOCR

**Tiếng Việt** · [English](BUILD.en.md) · [Về README](../README.md)

Các lệnh dưới đây chạy tại thư mục gốc của repo. Ứng dụng cần Python **3.12**, [uv](https://docs.astral.sh/uv/getting-started/installation/) và Tesseract có dữ liệu tiếng Việt (`vie`). OCRmyPDF dùng Ghostscript cho luồng PDF/A hiện tại. Model VietOCR được tải riêng khi cài, không nằm trong Git.

Nếu chưa có source:

```bash
git clone https://github.com/tvkhieu1998/VietLayerOCR.git
cd VietLayerOCR
```

Trên Windows, chạy hai lệnh này bằng PowerShell. Sau khi cài công cụ hệ thống, hãy mở terminal mới để cập nhật `PATH`.

## Chạy từ source

### macOS

Cài [Homebrew](https://brew.sh/) và [uv](https://docs.astral.sh/uv/getting-started/installation/) trước, rồi chạy:

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

Trong danh sách ngôn ngữ Tesseract phải có `vie`. Lệnh tải model kiểm tra SHA-256 trước khi lưu.

### Linux (Debian/Ubuntu)

Cài [uv](https://docs.astral.sh/uv/getting-started/installation/) và các công cụ hệ thống:

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

Các bản phân phối khác cần cài gói tương đương. Nếu Qt báo thiếu plugin `xcb`, cài thêm thư viện Qt/X11 mà bản phân phối yêu cầu.

### Windows (PowerShell)

Cài Git và [uv](https://docs.astral.sh/uv/getting-started/installation/). Cài **Tesseract 64-bit** có `vie` và **Ghostscript 64-bit**. Có thể dùng `winget install -e --id tesseract-ocr.tesseract` để cài Tesseract; tải Ghostscript từ [trang phát hành chính thức](https://ghostscript.com/releases/gsdnld.html). Nếu bộ cài Tesseract chưa có `vie`, thêm `vie.traineddata` từ [Tesseract tessdata](https://github.com/tesseract-ocr/tessdata) vào thư mục `tessdata` của nó.

Mở PowerShell mới và kiểm tra:

```powershell
tesseract --list-langs
gswin64c --version
uv --version
```

Nếu `gswin64c` chưa được nhận diện, thêm thư mục `bin` của Ghostscript vào `PATH`, rồi mở PowerShell mới. Sau đó chạy ở gốc repo:

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
uv pip install --python .venv\Scripts\python.exe --no-deps vietocr==0.3.13
.\.venv\Scripts\python.exe scripts\download_vietocr.py --model transformer
.\.venv\Scripts\python.exe desktop.py --check
.\.venv\Scripts\python.exe desktop.py
```

Trên cả ba nền tảng, `--check` chỉ kiểm tra Python và PySide6, không chạy OCR. Sau khi mở giao diện, hãy nhập một ảnh hoặc PDF scan ngắn để thử luồng PDF và TXT. Để dùng CLI, chạy `.venv/bin/python cli.py input.pdf output.pdf --export both` (Windows: `.\.venv\Scripts\python.exe`).

## Đóng gói ứng dụng desktop

Build trên **chính hệ điều hành và kiến trúc CPU đích**, sau khi hoàn thành phần “Chạy từ source”. Script build thêm model VietOCR, Python và các thư viện ứng dụng vào gói. Người dùng của gói vẫn cần Tesseract và `vie`; Linux/Windows cần Ghostscript trên máy chạy.

### macOS

```bash
uv pip install --python .venv/bin/python -r requirements-build.txt
.venv/bin/python scripts/build_desktop.py
open dist/VietLayerOCR.app
```

Kết quả: `dist/VietLayerOCR.app`. Ghostscript chỉ được đóng gói khi có `.venv/ghostscript/bin/gs`; với các bước Homebrew phía trên, Ghostscript vẫn là dependency trên máy chạy. Bản build này được ký cục bộ bởi PyInstaller, **chưa** có Developer ID hoặc notarization. Bản đã thử trên máy phát triển là Intel; build trên Apple Silicon nếu muốn phát hành bản native cho kiến trúc đó.

### Linux

```bash
uv pip install --python .venv/bin/python -r requirements-build.txt
.venv/bin/python scripts/build_desktop.py
./dist/VietLayerOCR/VietLayerOCR
```

Kết quả: toàn bộ thư mục `dist/VietLayerOCR/`. Khi sao chép sang máy khác, giữ nguyên thư mục và cài Tesseract/`vie` cùng Ghostscript trên máy đó. Nên thử gói trên bản phân phối Linux dự kiến hỗ trợ.

### Windows ZIP

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements-build.txt
.\.venv\Scripts\python.exe scripts\build_desktop.py
.\dist\VietLayerOCR\VietLayerOCR.exe
```

Kết quả: `dist\VietLayerOCR\` và `dist\VietLayerOCR-windows.zip`. Giải nén **toàn bộ** ZIP trước khi mở `VietLayerOCR.exe`; không chạy trực tiếp từ cửa sổ xem ZIP. Máy nhận ZIP phải cài Tesseract/`vie` và Ghostscript.

Gói đã build chạy OCRmyPDF thông qua worker bên trong ứng dụng, nên máy nhận gói không cần cài Python hoặc lệnh `ocrmypdf` riêng. Codex/Claude CLI là tính năng tùy chọn và phải cài, đăng nhập riêng. Gói có thể lớn vì chứa PyTorch, ONNX Runtime và model VietOCR.

## Khi gặp lỗi

| Triệu chứng | Kiểm tra |
| --- | --- |
| `No module named PySide6` | Dùng đúng `.venv/bin/python` hoặc `.\.venv\Scripts\python.exe`; chạy lại lệnh cài `requirements.txt`. |
| Thiếu model VietOCR | Chạy lại `scripts/download_vietocr.py --model transformer`; kiểm tra `models/vietocr/vgg_transformer.pth`. |
| Không có ngôn ngữ `vie` | Chạy `tesseract --list-langs`; cài dữ liệu tiếng Việt cho đúng bản Tesseract đang được gọi. |
| Không tìm thấy Ghostscript | Chạy `gs --version` (macOS/Linux) hoặc `gswin64c --version` (Windows), kiểm tra `PATH` và mở terminal mới. |
| PDF có chữ ký số bị từ chối | OCR sẽ làm thay đổi tài liệu và làm mất hiệu lực chữ ký. Dùng bản scan/ảnh nguồn hoặc bản PDF không ký nếu cần OCR. |
| Build thiếu icon/model | Đảm bảo đang ở gốc repo, có `assets/app_icon.png` và model đã tải. |

**Tình trạng xác minh:** macOS đã build và thử luồng OCR cục bộ. Linux và Windows cần thử thực tế trên máy tương ứng trước khi phát hành gói tải sẵn.
