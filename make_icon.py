"""Build a Windows icon without external image assets."""

from pathlib import Path
import struct

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen


size = 256
image = QImage(size, size, QImage.Format.Format_ARGB32)
image.fill(Qt.GlobalColor.transparent)
painter = QPainter(image)
painter.setRenderHint(QPainter.RenderHint.Antialiasing)
gradient = QLinearGradient(20, 20, 232, 232)
gradient.setColorAt(0, QColor("#277eff"))
gradient.setColorAt(1, QColor("#50c3ec"))
painter.setBrush(gradient)
painter.setPen(Qt.PenStyle.NoPen)
painter.drawRoundedRect(QRectF(12, 12, 232, 232), 58, 58)

white = QPen(QColor("#ffffff"), 18, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
painter.setPen(white)
painter.drawLine(QPointF(128, 57), QPointF(128, 150))
painter.drawLine(QPointF(87, 112), QPointF(128, 153))
painter.drawLine(QPointF(169, 112), QPointF(128, 153))
painter.drawLine(QPointF(77, 188), QPointF(179, 188))
painter.end()

target = Path(__file__).parent / "assets"
target.mkdir(exist_ok=True)
image.save(str(target / "icon.png"))
data = QByteArray()
buffer = QBuffer(data)
buffer.open(QIODevice.OpenModeFlag.WriteOnly)
image.save(buffer, "PNG")
buffer.close()
png = bytes(data)
header = struct.pack("<HHH", 0, 1, 1)
entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22)
(target / "icon.ico").write_bytes(header + entry + png)
