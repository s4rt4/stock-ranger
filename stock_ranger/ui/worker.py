"""Worker thread untuk menjalankan pipeline tanpa membekukan UI."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from ..core import profile_manager
from ..core.models import Metadata, OutputSettings
from ..core.pipeline import process_batch


class PipelineWorker(QThread):
    logLine = pyqtSignal(str)
    progressed = pyqtSignal(int)       # 0..100
    done = pyqtSignal(int, int)        # (sukses, total)

    def __init__(
        self,
        svgs: list[Path],
        meta: Metadata,
        settings: OutputSettings,
        prefer_swop: bool,
        manual_jpgs: dict[str, Path] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._svgs = svgs
        self._meta = meta
        self._settings = settings
        self._prefer_swop = prefer_swop
        self._manual_jpgs = manual_jpgs or {}

    def run(self):  # noqa: D401 — dijalankan di thread terpisah
        # Resolusi profile (first-run download SWOP bila diminta & belum ada)
        if self._prefer_swop and profile_manager.swop_path() is None:
            try:
                self.logLine.emit("Mengunduh profile SWOP v2 dari Adobe…")
                p = profile_manager.download_swop()
                self.logLine.emit(f"Profile tersimpan: {p.name}")
            except Exception as e:  # noqa: BLE001
                self.logLine.emit(f"Gagal unduh SWOP ({e}); pakai Ghostscript default")
        self._settings.icc_profile = profile_manager.resolve_profile(self._prefer_swop)
        prof = self._settings.icc_profile
        self.logLine.emit(f"ICC profile: {prof.name if prof else 'tidak ada (RGB!)'}")

        results = process_batch(
            self._svgs,
            self._meta,
            self._settings,
            log=self.logLine.emit,
            progress=self._on_progress,
            manual_jpgs=self._manual_jpgs,
        )
        ok = sum(1 for r in results if r.ok)
        self.progressed.emit(100)
        self.done.emit(ok, len(results))

    def _on_progress(self, index: int, total: int, stage: int, stage_total: int):
        if total <= 0:
            return
        pct = int((index * stage_total + stage) / (total * stage_total) * 100)
        self.progressed.emit(min(99, pct))
