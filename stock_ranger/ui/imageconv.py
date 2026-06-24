"""Konversi PIL.Image ↔ Qt. QImage aman dibuat di luar GUI thread."""

from __future__ import annotations

from PIL import Image
from PyQt6.QtGui import QImage, QPixmap


def pil_to_qimage(im: Image.Image) -> QImage:
    im = im.convert("RGBA")
    data = im.tobytes("raw", "RGBA")
    qimg = QImage(data, im.width, im.height, QImage.Format.Format_RGBA8888)
    return qimg.copy()  # detach dari buffer Python


def pil_to_qpixmap(im: Image.Image) -> QPixmap:
    return QPixmap.fromImage(pil_to_qimage(im))
