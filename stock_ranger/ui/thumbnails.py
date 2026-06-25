"""Render thumbnail file (SVG/EPS/JPG/PNG/PDF) ke QPixmap untuk content grid.

- SVG  : QtSvg (cepat, tanpa Inkscape).
- JPG/PNG: QPixmap langsung.
- EPS  : ekstrak embedded TIFF preview (DOS-EPS wrapper C5D0D3C6) via PIL bila ada,
         jika tidak → placeholder berlabel.
- Loader async (QThread) supaya buka folder besar tidak membekukan UI.
"""

from __future__ import annotations

import struct
from pathlib import Path

from PyQt6.QtCore import QRect, QRectF, QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from .imageconv import pil_to_qpixmap
from .theme import Color

RASTER_EXT = {".jpg", ".jpeg", ".png"}
SVG_EXT = {".svg"}
EPS_EXT = {".eps"}
VECTOR_EXT = {".pdf", ".ai"}
SUPPORTED_EXT = RASTER_EXT | SVG_EXT | EPS_EXT | VECTOR_EXT


def _canvas(size: int) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    return pix


def _fit_onto(src: QPixmap, size: int, *, bg: str | None = "#ffffff") -> QPixmap:
    """Scale src jaga aspect, taruh di tengah kanvas size×size (opsional bg)."""
    canvas = _canvas(size)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    if bg:
        p.fillRect(0, 0, size, size, QColor(bg))
    inner = size - 10
    scaled = src.scaled(
        inner, inner, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = (size - scaled.width()) // 2
    y = (size - scaled.height()) // 2
    p.drawPixmap(x, y, scaled)
    p.end()
    return canvas


def _placeholder(label: str, size: int) -> QPixmap:
    canvas = _canvas(size)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.fillRect(0, 0, size, size, QColor(Color.SURFACE_2))
    p.setPen(QColor(Color.TEXT_FAINT))
    f = p.font()
    f.setPointSize(max(9, size // 8))
    f.setBold(True)
    p.setFont(f)
    p.drawText(canvas.rect(), Qt.AlignmentFlag.AlignCenter, label)
    p.end()
    return canvas


def _render_eps_via_gs(path: Path, size: int) -> QPixmap | None:
    """Fallback EPS thumbnail: render via Ghostscript (untuk EPS Adobe yang
    preview TIFF-nya pakai offset absolut → tak terbaca PIL)."""
    import shutil
    import subprocess
    import tempfile
    if not shutil.which("gs"):
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="sr_epsthumb_") as td:
            png = Path(td) / "t.png"
            subprocess.run(
                ["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-dEPSCrop",
                 "-sDEVICE=png16m", "-r36", "-dGraphicsAlphaBits=4",
                 "-dTextAlphaBits=4", f"-sOutputFile={png}", str(path)],
                capture_output=True, timeout=20,
            )
            if png.exists():
                src = QPixmap(str(png))
                if not src.isNull():
                    return _fit_onto(src, size)
    except Exception:
        pass
    return None


def _extract_eps_preview(path: Path) -> QPixmap | None:
    """Ambil embedded TIFF preview dari DOS-EPS wrapper (C5D0D3C6)."""
    try:
        with open(path, "rb") as f:
            head = f.read(30)
            if head[:4] != b"\xc5\xd0\xd3\xc6":
                return None
            _, _, _, _, t_off, t_len, _ = struct.unpack("<IIIIIIH", head[4:30])
            if not t_len:
                return None
            f.seek(t_off)
            tiff = f.read(t_len)
        from io import BytesIO

        from PIL import Image
        im = Image.open(BytesIO(tiff)).convert("RGB")
        return pil_to_qpixmap(im)
    except Exception:
        return None


# Warna badge per format (selaras token tema).
_BADGE_COLORS = {
    "eps": "#6366f1", "jpg": "#22c55e", "jpeg": "#22c55e",
    "png": "#06b6d4", "svg": "#f5a623", "pdf": "#ef4444", "ai": "#ec4899",
}


def _draw_badge(pm: QPixmap, ext: str, size: int) -> QPixmap:
    """Gambar badge format (mis. EPS/JPG) di pojok kiri-bawah thumbnail."""
    label = ext.upper()
    color = _BADGE_COLORS.get(ext, "#646c7c")
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    f = p.font()
    f.setBold(True)
    f.setPointSize(max(7, size // 16))
    p.setFont(f)
    fm = QFontMetrics(f)
    pad_x, pad_y = 6, 2
    bw = fm.horizontalAdvance(label) + pad_x * 2
    bh = fm.height() + pad_y * 2
    margin = 6
    x, y = margin, size - bh - margin
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(x, y, bw, bh, 5, 5)
    p.setPen(QColor("#ffffff"))
    p.drawText(QRect(x, y, bw, bh), Qt.AlignmentFlag.AlignCenter, label)
    p.end()
    return pm


def render_thumbnail(path: Path, size: int) -> QPixmap:
    """Render thumbnail + badge format. Dipanggil di worker thread."""
    pm = _render_base(path, size)
    return _draw_badge(pm, path.suffix.lower().lstrip("."), size)


def _render_base(path: Path, size: int) -> QPixmap:
    """Render isi thumbnail (tanpa badge)."""
    ext = path.suffix.lower()
    try:
        if ext in SVG_EXT:
            r = QSvgRenderer(str(path))
            if r.isValid():
                vb = r.viewBoxF()
                w = vb.width() or size
                h = vb.height() or size
                scale = (size - 10) / max(w, h)
                tw, th = w * scale, h * scale
                canvas = _canvas(size)
                p = QPainter(canvas)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.fillRect(0, 0, size, size, QColor("#ffffff"))
                r.render(p, QRectF((size - tw) / 2, (size - th) / 2, tw, th))
                p.end()
                return canvas
            return _placeholder("SVG", size)
        if ext in RASTER_EXT:
            src = QPixmap(str(path))
            if not src.isNull():
                return _fit_onto(src, size, bg=Color.SURFACE_2)
            return _placeholder(ext[1:].upper(), size)
        if ext in EPS_EXT:
            pm = _extract_eps_preview(path)
            if pm:
                return _fit_onto(pm, size)
            pm = _render_eps_via_gs(path, size)  # fallback EPS Adobe
            return pm if pm else _placeholder("EPS", size)
        if ext in VECTOR_EXT:
            return _placeholder(ext[1:].upper(), size)
    except Exception:
        pass
    return _placeholder("?", size)


class ThumbnailLoader(QThread):
    """Render thumbnail daftar file di background, emit per-file."""

    ready = pyqtSignal(int, QPixmap)  # (row, pixmap)

    def __init__(self, files: list[Path], size: int, parent=None):
        super().__init__(parent)
        self._files = files
        self._size = size
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        for row, path in enumerate(self._files):
            if self._stop:
                return
            pm = render_thumbnail(path, self._size)
            if self._stop:
                return
            self.ready.emit(row, pm)


__all__ = ["render_thumbnail", "ThumbnailLoader", "SUPPORTED_EXT", "QSize"]
