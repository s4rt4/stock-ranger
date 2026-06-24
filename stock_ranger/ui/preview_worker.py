"""Worker thread untuk generate live preview + analisis gamut (non-blocking)."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from ..core import preview
from .imageconv import pil_to_qimage


class PreviewWorker(QThread):
    # rgb QImage, cmyk QImage, gamut_out, path (untuk cek relevansi)
    ready = pyqtSignal(object, object, int, str)
    failed = pyqtSignal(str, str)

    def __init__(self, svg: Path, icc: Path | None, parent=None):
        super().__init__(parent)
        self._svg = Path(svg)
        self._icc = icc

    def run(self):
        try:
            res = preview.analyze(self._svg, self._icc, max_px=560)
            self.ready.emit(
                pil_to_qimage(res.rgb),
                pil_to_qimage(res.cmyk_sim),
                res.gamut_out,
                str(self._svg),
            )
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e), str(self._svg))
