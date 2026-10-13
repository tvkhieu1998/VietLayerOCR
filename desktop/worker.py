"""Run the OCR pipeline off the GUI thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from vietlayer.core import OcrConfig, process_document


class OcrWorker(QObject):
    progress = Signal(str)
    completed = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, source_path, output_path, config: OcrConfig):
        super().__init__()
        self.source_path = source_path
        self.output_path = output_path
        self.config = config

    @Slot()
    def run(self):
        try:
            result = process_document(self.source_path, self.output_path, self.config, self.progress.emit)
            self.completed.emit(result)
        except Exception as error:
            self.failed.emit(error)
        finally:
            self.finished.emit()
