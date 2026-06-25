"""Render thumbnail file (SVG/EPS/JPG/PNG/PDF) untuk content grid.

PENTING: render menghasilkan QImage (BUKAN QPixmap). QPixmap tidak aman dibuat di
luar GUI thread; loader bekerja di QThread, jadi semua di sini pakai QImage dan
konversi ke QPixmap dilakukan di GUI thread (lihat ContentGrid._set_thumb).

- SVG  : QtSvg (cepat, tanpa Inkscape).
- JPG/PNG: QImage langsung.
- EPS  : ekstrak embedded TIFF preview (DOS-EPS wrapper) via PIL; jika gagal
         (mis. EPS Adobe offset absolut) → fallback render Ghostscript; lalu placeholder.
- Badge format (EPS/JPG/…) digambar di pojok tiap thumbnail.
"""

from __future__ import annotations

import struct
from pathlib import Path

from PyQt6.QtCore import QRect, QRectF, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer

from .imageconv import pil_to_qimage
from .theme import Color

RASTER_EXT = {".jpg", ".jpeg", ".png"}
SVG_EXT = {".svg"}
EPS_EXT = {".eps"}
VECTOR_EXT = {".pdf", ".ai"}
SUPPORTED_EXT = RASTER_EXT | SVG_EXT | EPS_EXT | VECTOR_EXT


def _canvas(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 0, 0, 0))
    return img


def _fit_onto(src: QImage, size: int, *, bg: str | None = "#ffffff") -> QImage:
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
    p.drawImage(x, y, scaled)
    p.end()
    return canvas


def _placeholder(label: str, size: int) -> QImage:
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


def _render_eps_via_gs(path: Path, size: int) -> QImage | None:
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
                src = QImage(str(png))
                if not src.isNull():
                    return _fit_onto(src, size)
    except Exception:
        pass
    return None


def _extract_eps_preview(path: Path) -> QImage | None:
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
        return pil_to_qimage(im)
    except Exception:
        return None


# Warna badge per format (selaras token tema).
_BADGE_COLORS = {
    "eps": "#6366f1", "jpg": "#22c55e", "jpeg": "#22c55e",
    "png": "#06b6d4", "svg": "#f5a623", "pdf": "#ef4444", "ai": "#ec4899",
}


def _draw_badge(img: QImage, ext: str, size: int) -> QImage:
    """Gambar badge format (mis. EPS/JPG) di pojok kiri-bawah thumbnail."""
    label = ext.upper()
    color = _BADGE_COLORS.get(ext, "#646c7c")
    p = QPainter(img)
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
    return img


def render_thumbnail(path: Path, size: int) -> QImage:
    """Render thumbnail + badge format → QImage. Aman dipanggil di worker thread."""
    img = _render_base(path, size)
    return _draw_badge(img, path.suffix.lower().lstrip("."), size)


def _render_base(path: Path, size: int) -> QImage:
    """Render isi thumbnail (tanpa badge) → QImage."""
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
            src = QImage(str(path))
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
    """Render thumbnail daftar file di background, emit QImage per-file."""

    ready = pyqtSignal(int, QImage)  # (row, image)

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
            img = render_thumbnail(path, self._size)
            if self._stop:
                return
            self.ready.emit(row, img)


__all__ = ["render_thumbnail", "ThumbnailLoader", "SUPPORTED_EXT", "SVG_EXT"]
