"""Accessible switch control for optional AI processing."""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QCheckBox


class AiSwitch(QCheckBox):
    CONTENT_INSET = 14

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(34)

    def hitButton(self, position):
        return self.rect().contains(position)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = (self.height() - 22) // 2
        track_left = self.width() - self.CONTENT_INSET - 42
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#E6C49B" if self.isChecked() else "#B88163"))
        painter.drawRoundedRect(track_left, top, 42, 22, 11, 11)
        painter.setBrush(QColor("#FFF7EF"))
        painter.drawEllipse(track_left + (22 if self.isChecked() else 3), top + 3, 16, 16)
        painter.setPen(QColor("#FFF5E9" if self.isEnabled() else "#D7C0AF"))
        painter.drawText(QRect(self.CONTENT_INSET, 0,
                               track_left - self.CONTENT_INSET - 8, self.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
        painter.end()
