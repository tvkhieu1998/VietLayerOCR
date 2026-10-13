"""Render source and OCR PDF pages using QtPdf, with review highlights."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter, QPen, QPixmap
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from .icons import outline_icon


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


class DocumentPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._path: Path | None = None
        self._pdf = QPdfDocument(self)
        self._image = QImage()
        self._image_page_count = 0
        self._page_index = 0
        self._zoom = 1.0
        self._highlight: tuple[list[int], list[int]] | None = None
        self._rendered = QImage()
        self._crop_image = QImage()
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._label)
        self.empty_state = QWidget(self)
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setContentsMargins(12, 12, 12, 12)
        empty_layout.addStretch(1)
        center_row = QHBoxLayout()
        center_row.addStretch(1)
        card = QFrame()
        card.setObjectName("previewEmptyCard")
        card.setFixedWidth(330)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(12)
        self.empty_icon = QLabel()
        self.empty_icon.setObjectName("previewEmptyIcon")
        self.empty_icon.setPixmap(outline_icon("text", "#895D45", 60).pixmap(60, 60))
        self.empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.empty_icon)
        self.empty_title = QLabel("Chưa có tài liệu")
        self.empty_title.setObjectName("previewEmptyTitle")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.empty_title)
        self.empty_description = QLabel("Thêm PDF hoặc ảnh để xem trước và nhận dạng văn bản.")
        self.empty_description.setObjectName("previewEmptyDescription")
        self.empty_description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_description.setWordWrap(True)
        card_layout.addWidget(self.empty_description)
        center_row.addWidget(card)
        center_row.addStretch(1)
        empty_layout.addLayout(center_row)
        empty_layout.addStretch(1)
        self._stack = QStackedWidget(self)
        self._stack.addWidget(self.empty_state)
        self._stack.addWidget(self._scroll)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

    @property
    def page_count(self) -> int:
        if self._path is None:
            return 0
        return self._image_page_count if self._path.suffix.lower() in IMAGE_SUFFIXES else self._pdf.pageCount()

    def load_document(self, path: Path) -> bool:
        path = Path(path)
        self._path = path
        self._page_index = 0
        self._highlight = None
        self._image = QImage()
        self._image_page_count = 0
        self._crop_image = QImage()
        self._pdf.close()
        if path.suffix.lower() in IMAGE_SUFFIXES:
            reader = QImageReader(str(path))
            self._image_page_count = max(1, reader.imageCount())
            self._image = reader.read()
            success = not self._image.isNull()
        else:
            self._pdf.load(str(path))
            success = self._pdf.pageCount() > 0
        if not success:
            self._path = None
            self.empty_title.setText("Không mở được tài liệu")
            self.empty_description.setText("Kiểm tra tệp PDF hoặc ảnh rồi thử lại.")
            self._stack.setCurrentWidget(self.empty_state)
            return False
        self._stack.setCurrentWidget(self._scroll)
        self.render_page()
        QTimer.singleShot(0, self.render_page)
        return True

    def set_page(self, page_index: int) -> None:
        if 0 <= page_index < self.page_count:
            self._page_index = page_index
            self._highlight = None
            self._crop_image = QImage()
            if self._path.suffix.lower() in IMAGE_SUFFIXES:
                reader = QImageReader(str(self._path))
                if reader.jumpToImage(page_index):
                    self._image = reader.read()
            self.render_page()

    def set_highlight(self, bbox: list[int] | None, image_size: list[int] | None) -> None:
        self._highlight = (bbox, image_size) if bbox and image_size else None
        self.render_page()

    def change_zoom(self, multiplier: float) -> None:
        self._zoom = max(0.5, min(2.5, self._zoom * multiplier))
        self.render_page()

    def fit_width(self) -> None:
        self._zoom = 1.0
        self.render_page()

    def _source_image(self, target_width: int) -> QImage:
        if self._path is None:
            return QImage()
        if self._path.suffix.lower() in IMAGE_SUFFIXES:
            return self._image.scaledToWidth(target_width, Qt.TransformationMode.SmoothTransformation)
        size = self._pdf.pagePointSize(self._page_index)
        if size.width() <= 0:
            return QImage()
        height = max(1, round(target_width * size.height() / size.width()))
        return self._pdf.render(self._page_index, QSize(target_width, height))

    def render_page(self) -> None:
        if self._path is None:
            return
        available_width = max(240, self._scroll.viewport().width() - 36)
        target_width = max(240, round(available_width * self._zoom))
        image = self._source_image(target_width)
        if image.isNull():
            self._label.setText("Không hiển thị được trang")
            return
        self._rendered = image
        painted = image.copy()
        if self._highlight:
            box, image_size = self._highlight
            if image_size[0] and image_size[1]:
                x = box[0] * painted.width() / image_size[0]
                y = box[1] * painted.height() / image_size[1]
                width = (box[2] - box[0]) * painted.width() / image_size[0]
                height = (box[3] - box[1]) * painted.height() / image_size[1]
                painter = QPainter(painted)
                painter.setPen(QPen(QColor("#A45F3B"), 3))
                painter.setBrush(QColor(164, 95, 59, 42))
                painter.drawRoundedRect(round(x), round(y), max(2, round(width)), max(2, round(height)), 3, 3)
                painter.end()
        self._label.setPixmap(QPixmap.fromImage(painted))
        self._label.resize(painted.size())

    def crop_region(self, bbox: list[int] | None, image_size: list[int] | None) -> QPixmap:
        if self._rendered.isNull() or not bbox or not image_size or not all(image_size):
            return QPixmap()
        if self._crop_image.isNull():
            self._crop_image = self._image if self._path.suffix.lower() in IMAGE_SUFFIXES else self._source_image(2200)
        image = self._crop_image
        x = max(0, round(bbox[0] * image.width() / image_size[0]))
        y = max(0, round(bbox[1] * image.height() / image_size[1]))
        width = max(1, round((bbox[2] - bbox[0]) * image.width() / image_size[0]))
        height = max(1, round((bbox[3] - bbox[1]) * image.height() / image_size[1]))
        return QPixmap.fromImage(image.copy(x, y, width, height))

    def thumbnail(self, page_index: int, width: int = 145) -> QPixmap:
        if not 0 <= page_index < self.page_count:
            return QPixmap()
        if self._path.suffix.lower() in IMAGE_SUFFIXES:
            reader = QImageReader(str(self._path))
            if not reader.jumpToImage(page_index):
                return QPixmap()
            image = reader.read().scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
        else:
            size = self._pdf.pagePointSize(page_index)
            height = round(width * size.height() / size.width()) if size.width() else width
            image = self._pdf.render(page_index, QSize(width, max(1, height)))
        return QPixmap.fromImage(image)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._path is not None and self._zoom == 1.0:
            self.render_page()
