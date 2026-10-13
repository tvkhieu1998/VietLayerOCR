"""Document OCR API shared by the CLI and desktop UI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal


SUPPORTED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = PROJECT_ROOT / "models" / "vietocr"


@dataclass(frozen=True)
class OcrConfig:
    language: str = "vie"
    page_mode: Literal["skip", "force"] = "skip"
    model: Literal["transformer", "seq2seq"] = "transformer"
    model_dir: Path | None = None
    pdfa: bool = True
    export_format: Literal["pdf", "txt", "both"] = "both"
    deskew: bool = True
    rotate_pages: bool = True
    invalidate_digital_signatures: bool = False
    ai_provider: Literal["codex-cli", "claude-cli", "openai-api", "anthropic-api", "gemini-api"] | None = None
    ai_model: str | None = None
    ai_effort: str | None = None
    ai_api_key: str | None = field(default=None, repr=False)
    ai_timeout_seconds: int = 180
    evidence_dir: Path | None = None
    timeout_minutes: int = 30
    corrections: dict[str, dict[str, str | dict]] = field(default_factory=dict)


@dataclass(frozen=True)
class OcrResult:
    pdf_path: Path | None
    text_path: Path | None
    page_count: int
    character_count: int
    elapsed_seconds: float
    report: list[dict]
    page_texts: list[str] = field(default_factory=list)


class OcrError(RuntimeError):
    """The document could not be processed by OCRmyPDF or its dependencies."""


class DigitalSignatureError(OcrError):
    """OCR needs explicit consent to invalidate a signed PDF copy."""


def _split_page_texts(raw_text: str, page_count: int) -> list[str]:
    pages = raw_text.split("\f")
    return [pages[index].strip() if index < len(pages) else "" for index in range(page_count)]


def _extract_text(pdf_path: Path) -> str:
    from pdfminer.high_level import extract_text

    return extract_text(str(pdf_path)) or ""


def _count_pages(pdf_path: Path) -> int:
    import pikepdf

    with pikepdf.open(pdf_path) as pdf:
        return len(pdf.pages)


def process_document(
    input_path: str | Path,
    output_pdf_path: str | Path,
    config: OcrConfig | None = None,
    progress: Callable[[str], None] | None = None,
) -> OcrResult:
    """Create a searchable PDF/A-2 and/or TXT with local Tesseract and VietOCR."""
    config = config or OcrConfig()
    input_path = Path(input_path).expanduser().resolve()
    output_pdf_path = Path(output_pdf_path).expanduser().resolve()
    if input_path == output_pdf_path:
        raise ValueError("Tệp đầu ra phải khác tệp đầu vào.")
    if not input_path.is_file() or input_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError("Cần tệp PDF, PNG, JPG hoặc TIFF hợp lệ.")
    if output_pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Tệp đầu ra phải có đuôi .pdf.")
    if config.language not in {"vie", "eng", "vie+eng"}:
        raise ValueError("Ngôn ngữ OCR không hợp lệ.")
    if config.page_mode not in {"skip", "force"}:
        raise ValueError("Chế độ OCR không hợp lệ.")
    if config.model not in {"transformer", "seq2seq"}:
        raise ValueError("Chế độ VietOCR không hợp lệ.")
    if config.export_format not in {"pdf", "txt", "both"}:
        raise ValueError("Định dạng xuất phải là pdf, txt hoặc both.")
    if config.timeout_minutes <= 0:
        raise ValueError("Thời gian tối đa phải lớn hơn 0.")
    if config.ai_provider not in {None, "codex-cli", "claude-cli", "openai-api", "anthropic-api", "gemini-api"}:
        raise ValueError("Provider AI chưa được hỗ trợ.")
    if config.ai_provider and config.ai_provider.endswith("-api") and not config.ai_api_key:
        raise ValueError("Cần API key để sử dụng AI qua API.")
    if config.ai_effort not in {None, "low", "medium", "high", "xhigh", "max"}:
        raise ValueError("Mức suy luận AI không hợp lệ.")
    if config.ai_timeout_seconds <= 0:
        raise ValueError("Thời gian chờ AI phải lớn hơn 0.")

    config_name = "vgg-transformer" if config.model == "transformer" else "vgg-seq2seq"
    model_dir = Path(config.model_dir or DEFAULT_MODEL_DIR).expanduser().resolve()
    required_files = ("base.yml", f"{config_name}.yml", f"{config_name.replace('-', '_')}.pth")
    missing_files = [name for name in required_files if not (model_dir / name).is_file()]
    if missing_files:
        raise FileNotFoundError(f"Thiếu mô hình VietOCR trong {model_dir}: {', '.join(missing_files)}")
    for executable in ("ocrmypdf", "tesseract"):
        if not shutil.which(executable):
            raise FileNotFoundError(f"Chưa cài hoặc chưa đưa {executable} vào PATH.")
    if config.ai_provider and config.ai_provider.endswith("-cli"):
        executable = "codex" if config.ai_provider == "codex-cli" else "claude"
        if not shutil.which(executable):
            raise FileNotFoundError(f"Chưa cài hoặc chưa đưa {executable} CLI vào PATH.")

    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    started_at = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="vietlayer-", dir=output_pdf_path.parent) as temporary_directory:
        temporary_directory = Path(temporary_directory)
        temporary_pdf = temporary_directory / "result.pdf"
        report_dir = temporary_directory / "reports"
        environment = os.environ.copy()
        environment.update({
            "VIETLAYER_ENABLE": "1",
            "VIETLAYER_REPORT_DIR": str(report_dir),
            "VIETOCR_MODEL_NAME": config.model,
            "VIETOCR_MODEL_DIR": str(model_dir),
        })
        for name in ("VIETLAYER_AI_PROVIDER", "VIETLAYER_AI_TIMEOUT_SECONDS", "VIETLAYER_AI_MODEL",
                     "VIETLAYER_AI_EFFORT", "VIETLAYER_AI_API_KEY"):
            environment.pop(name, None)
        if config.ai_provider:
            environment["VIETLAYER_AI_PROVIDER"] = config.ai_provider
            environment["VIETLAYER_AI_TIMEOUT_SECONDS"] = str(config.ai_timeout_seconds)
            if config.ai_model:
                environment["VIETLAYER_AI_MODEL"] = config.ai_model
            if config.ai_effort:
                environment["VIETLAYER_AI_EFFORT"] = config.ai_effort
            if config.ai_api_key:
                environment["VIETLAYER_AI_API_KEY"] = config.ai_api_key
        if config.evidence_dir:
            environment["VIETLAYER_EVIDENCE_DIR"] = str(Path(config.evidence_dir).expanduser().resolve())
        if config.corrections:
            correction_path = temporary_directory / "corrections.json"
            correction_path.write_text(json.dumps(config.corrections, ensure_ascii=False), encoding="utf-8")
            environment["VIETLAYER_CORRECTIONS_PATH"] = str(correction_path)
        command = [
            "ocrmypdf", "-l", config.language,
            "--output-type", "pdfa-2" if config.pdfa else "pdf",
            "--force-ocr" if config.page_mode == "force" else "--skip-text",
            "--jobs", "1",
        ]
        if config.deskew:
            command.append("--deskew")
        if config.rotate_pages:
            command.append("--rotate-pages")
        if config.invalidate_digital_signatures:
            command.append("--invalidate-digital-signatures")
        if input_path.suffix.lower() != ".pdf":
            command += ["--image-dpi", "300"]
        command += ["--plugin", str(PROJECT_ROOT / "ocr_plugin.py"), str(input_path), str(temporary_pdf)]
        if progress:
            progress("Đang nhận dạng")
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=config.timeout_minutes * 60,
                env=environment,
            )
        except subprocess.TimeoutExpired as error:
            raise OcrError("Xử lý quá thời gian cho phép.") from error
        if completed.returncode != 0 or not temporary_pdf.is_file():
            detail = (completed.stderr or completed.stdout or "")[-1500:].strip()
            if not config.invalidate_digital_signatures and (
                "DigitalSignatureError" in detail or "digital signature" in detail.lower()
            ):
                raise DigitalSignatureError(
                    "Tài liệu có chữ ký số. Tạo bản OCR mới sẽ làm chữ ký số trên bản xuất mất hiệu lực."
                )
            raise OcrError(f"OCRmyPDF không hoàn thành (mã {completed.returncode}). {detail}")

        page_count = _count_pages(temporary_pdf)
        raw_text = _extract_text(temporary_pdf)
        page_texts = _split_page_texts(raw_text, page_count)
        text = raw_text.replace("\f", "\n\n").strip()
        report = [json.loads(path.read_text(encoding="utf-8"))
                  for path in sorted(report_dir.glob("page_*.json"))]
        temporary_text = temporary_directory / "result.txt"
        temporary_text.write_text(text, encoding="utf-8")
        output_text_path = output_pdf_path.with_suffix(".txt")
        include_pdf = config.export_format in {"pdf", "both"}
        include_text = config.export_format in {"txt", "both"}
        if include_pdf:
            temporary_pdf.replace(output_pdf_path)
        if include_text:
            temporary_text.replace(output_text_path)
    if progress:
        progress("Hoàn thành")
    return OcrResult(
        output_pdf_path if include_pdf else None,
        output_text_path if include_text else None,
        page_count,
        len(text),
        round(time.monotonic() - started_at, 2),
        report,
        page_texts,
    )
