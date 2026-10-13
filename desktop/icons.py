"""Small outline icons that match the warm desktop theme."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


def outline_icon(name: str, color: str = "#FFF8F1", size: int = 24) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 24, size / 24)
    painter.setPen(QPen(QColor(color), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if name == "add":
        painter.drawRoundedRect(3, 3, 15, 18, 2, 2)
        painter.drawLine(14, 3, 19, 8)
        painter.drawLine(18, 8, 18, 12)
        painter.drawLine(15, 17, 22, 17)
        painter.drawLine(18, 14, 18, 21)
    elif name == "pdf":
        painter.drawRoundedRect(4, 2, 14, 20, 2, 2)
        painter.drawLine(13, 2, 18, 7)
        painter.drawLine(13, 2, 13, 7)
        painter.drawLine(13, 7, 18, 7)
        painter.drawLine(8, 15, 15, 15)
        painter.drawLine(12, 12, 15, 15)
        painter.drawLine(12, 18, 15, 15)
    elif name == "text":
        painter.drawRoundedRect(4, 2, 16, 20, 2, 2)
        painter.drawLine(8, 9, 16, 9)
        painter.drawLine(8, 13, 16, 13)
        painter.drawLine(8, 17, 14, 17)
    elif name == "scan":
        painter.drawLine(3, 9, 3, 4)
        painter.drawLine(3, 4, 8, 4)
        painter.drawLine(16, 4, 21, 4)
        painter.drawLine(21, 4, 21, 9)
        painter.drawLine(3, 15, 3, 20)
        painter.drawLine(3, 20, 8, 20)
        painter.drawLine(16, 20, 21, 20)
        painter.drawLine(21, 20, 21, 15)
        painter.drawRoundedRect(8, 9, 8, 6, 2, 2)
    elif name == "save":
        painter.drawRoundedRect(4, 3, 16, 18, 2, 2)
        painter.drawRect(8, 3, 8, 6)
        painter.drawRect(8, 14, 8, 7)
    painter.end()
    return QIcon(pixmap)
