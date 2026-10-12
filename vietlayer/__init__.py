"""Local Vietnamese OCR pipeline for searchable PDFs."""

from .core import OcrConfig, OcrError, OcrResult, process_document

__all__ = ["OcrConfig", "OcrError", "OcrResult", "process_document"]
