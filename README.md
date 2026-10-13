# VietLayerOCR

**Tiếng Việt** · [English](README.en.md)

VietLayerOCR là ứng dụng desktop nhận dạng tài liệu scan tiếng Việt. Ứng dụng tạo PDF/A có lớp chữ để tìm kiếm, sao chép và xuất thêm file TXT. Luồng OCR cục bộ dùng OCRmyPDF, Tesseract, RapidOCR và VietOCR; người dùng có thể bật AI để đối chiếu những vùng chữ chưa chắc chắn.

![Biểu tượng VietLayerOCR](assets/app_icon.png)

## Bắt đầu

Bạn có thể [chạy từ source](docs/BUILD.md#chạy-từ-source) hoặc [tự build ứng dụng desktop](docs/BUILD.md#đóng-gói-ứng-dụng-desktop) trên macOS, Linux và Windows. Hướng dẫn gồm các dependency cần cài, lệnh kiểm tra và vị trí file sau khi build.

Để thử ngay trên macOS sau khi đã cài [Homebrew](https://brew.sh/) và [uv](https://docs.astral.sh/uv/getting-started/installation/), mở Terminal tại thư mục repo:

```bash
brew install tesseract tesseract-lang ghostscript
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
uv pip install --python .venv/bin/python --no-deps vietocr==0.3.13
.venv/bin/python scripts/download_vietocr.py --model transformer
.venv/bin/python desktop.py --check
.venv/bin/python desktop.py
```

Nếu chưa có repo, dùng `git clone https://github.com/tvkhieu1998/VietLayerOCR.git` rồi `cd VietLayerOCR` trước các lệnh trên. Hãy kiểm tra `vie` xuất hiện trong `tesseract --list-langs`. Hướng dẫn đầy đủ cho [Linux](docs/BUILD.md#linux-debianubuntu) và [Windows](docs/BUILD.md#windows-powershell) nằm trong tài liệu build.

> **Tình trạng build:** Bản macOS đã được build và chạy thử cục bộ. Lệnh build Linux và Windows đã được chuẩn bị nhưng chưa xác nhận trên hai hệ điều hành đó. Bản `.app` hiện chưa ký bằng Developer ID và chưa notarize.

## Cách dùng

1. Chọn **Thêm tài liệu** để mở PDF hoặc ảnh.
2. Bấm **Nhận dạng tài liệu**. Mặc định toàn bộ OCR chạy cục bộ; không cần tài khoản AI.
3. Chọn **Chi tiết** để xem và sửa vùng chữ cần đối chiếu; chọn **Tổng thể text** để đọc và sao chép chữ của trang.
4. Bấm **Xuất PDF** để lưu PDF có lớp chữ hoặc **Xuất TXT** để lưu văn bản. Kiểm tra kết quả với bản scan trước khi dùng.

Nếu muốn dùng AI, vào **Cài đặt OCR**, chọn Provider CLI hoặc API AI rồi kiểm tra kết nối. Khi bật **Sử dụng AI**, ảnh crop và các bản đọc OCR của vùng cần đối chiếu có thể được gửi tới nhà cung cấp đã chọn. API key chỉ được giữ trong phiên ứng dụng, không lưu vào QSettings. Nếu AI lỗi, ứng dụng giữ kết quả OCR cục bộ và báo trạng thái.

## Pipeline

1. OCRmyPDF chuẩn bị trang, xử lý xoay/nghiêng và tạo PDF/A.
2. Tesseract đọc trang đã tăng tương phản, tạo chữ và tọa độ hOCR.
3. RapidOCR phát hiện vùng chữ; VietOCR đọc lại từng vùng.
4. Bộ chọn so sánh hai bản đọc, giữ các số mâu thuẫn để người dùng kiểm tra. AI là lớp đối chiếu tùy chọn cho vùng chưa chắc chắn.
5. Chữ đã chọn được đặt vào đúng tọa độ của lớp chữ PDF; ứng dụng đồng thời xuất TXT.

## Dùng dòng lệnh và phát triển

Sau khi [cài môi trường chạy từ source](docs/BUILD.md#chạy-từ-source):

```bash
.venv/bin/python cli.py input.pdf output.pdf --export both --language vie
.venv/bin/python -m unittest discover -s tests -v
```

Trên Windows, thay `.venv/bin/python` bằng `.\.venv\Scripts\python.exe`. CLI có `--export pdf|txt|both`, `--force-ocr` để đọc lại PDF đã có chữ và `--no-pdfa` để xuất PDF thường. Python API là `vietlayer.process_document(input_path, output_pdf_path, OcrConfig(...))`. [Báo cáo kiểm thử luồng AI](reports/ai-core-review.html) có bằng chứng theo từng giai đoạn.

## Giới hạn hiện tại

- Tesseract và dữ liệu tiếng Việt phải được cài trên máy chạy ứng dụng. Linux và Windows cũng cần Ghostscript; bản macOS chỉ đóng gói Ghostscript khi tìm thấy `.venv/ghostscript/bin/gs` lúc build.
- Vùng tô sáng dùng tọa độ ảnh OCR quy đổi lên trang PDF. Với trang bị xoay hoặc chỉnh nghiêng mạnh, cần kiểm tra vị trí vùng chữ bằng mắt.
- Sau khi sửa tay một vùng, ứng dụng chạy lại OCR để PDF và TXT nhất quán; thời gian chờ gần tương đương lần xử lý đầu.
- Gói build có thể lớn vì chứa PyTorch, ONNX Runtime và model VietOCR. Công cụ Codex/Claude CLI, nếu dùng, cần cài riêng.

Tên file, hàm và biến trong source dùng tiếng Anh; chữ hiển thị cho người dùng dùng tiếng Việt.

## Giấy phép

Phần mã nguồn do dự án phát triển được phát hành theo [MIT License](LICENSE). Repo hiện cung cấp source và hướng dẫn để người dùng tự build; chưa phát hành gói ứng dụng tải sẵn. PySide6, Ghostscript, VietOCR và các thành phần bên thứ ba giữ giấy phép riêng của chúng. Nếu phân phối lại ứng dụng đã đóng gói, cần kiểm tra và tuân thủ giấy phép của những thành phần được đưa vào gói.
