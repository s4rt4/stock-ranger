"""MainWindow — layout ala Adobe Bridge.

Kiri: folder tree (filesystem). Tengah: content grid thumbnail. Kanan: inspector
(File Properties + Metadata + Export). Bawah: log panel + statusbar.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QSizePolicy,
    QSlider,
    QSplitter,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core.models import JpgMode, OutputSettings
from . import icons
from .browser import ContentGrid, FolderTree
from .inspector import Inspector
from .theme import Color, stylesheet
from .thumbnails import SVG_EXT
from .worker import PipelineWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stock Ranger")
        self.resize(1320, 860)
        self.setMinimumSize(1000, 600)
        self.setStyleSheet(stylesheet())

        self._worker: PipelineWorker | None = None
        self._current_folder: Path | None = None

        self._build_toolbar()
        self._build_body()
        self._build_statusbar()

        self.tree.reveal(Path.home())

    # ---------- toolbar ----------
    def _build_toolbar(self):
        tb = QToolBar()
        tb.setObjectName("topbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        brand = QWidget()
        bl = QHBoxLayout(brand)
        bl.setContentsMargins(8, 0, 12, 0)
        bl.setSpacing(2)
        name = QLabel("Stock Ranger")
        name.setObjectName("brand")
        dot = QLabel("●")
        dot.setObjectName("brandDot")
        bl.addWidget(name)
        bl.addWidget(dot)
        tb.addWidget(brand)
        tb.addWidget(self._vsep())

        # breadcrumb path
        self.path_label = QLabel("")
        self.path_label.setStyleSheet(f"color:{Color.TEXT_DIM};font-size:12px;padding:0 6px;")
        tb.addWidget(self.path_label)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        # thumbnail size slider
        zo = QLabel()
        zo.setPixmap(icons.pixmap("image", Color.ICON, 16))
        tb.addWidget(zo)
        self.thumb_slider = QSlider(Qt.Orientation.Horizontal)
        self.thumb_slider.setRange(96, 320)
        self.thumb_slider.setValue(150)
        self.thumb_slider.setFixedWidth(120)
        self.thumb_slider.valueChanged.connect(self._on_thumb_size)
        tb.addWidget(self.thumb_slider)
        tb.addWidget(self._vsep())

        self.log_action = self._add_tool(tb, "list", "Toggle log panel", self._toggle_log, checkable=True)

        cta = QWidget()
        cl = QHBoxLayout(cta)
        cl.setContentsMargins(6, 0, 2, 0)
        self.cta_btn = QToolButton()
        self.cta_btn.setObjectName("cta")
        self.cta_btn.setText("  Process  ")
        self.cta_btn.setIcon(icons.icon("zap", "#08240f", 18))
        self.cta_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.cta_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cta_btn.clicked.connect(self._process)
        cl.addWidget(self.cta_btn)
        tb.addWidget(cta)

    def _add_tool(self, tb, icon_name, tip, slot, checkable=False):
        act = QAction(icons.icon(icon_name, Color.ICON, 20), tip, self)
        act.setToolTip(tip)
        act.setCheckable(checkable)
        if slot:
            act.triggered.connect(slot)
        tb.addAction(act)
        return act

    def _vsep(self) -> QFrame:
        s = QFrame()
        s.setObjectName("vsep")
        s.setFrameShape(QFrame.Shape.VLine)
        s.setFixedHeight(22)
        return s

    # ---------- body ----------
    def _build_body(self):
        central = QWidget()
        central.setObjectName("root")
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("mainSplit")
        self.splitter.setHandleWidth(1)

        self.tree = FolderTree()
        self.tree.folderSelected.connect(self._on_folder)

        self.grid = ContentGrid()
        self.grid.selectionChangedFiles.connect(self._on_grid_selection)

        self.inspector = Inspector()
        self.inspector.processRequested.connect(self._process)

        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(self.grid)
        self.splitter.addWidget(self.inspector)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([240, 720, 360])

        outer.addWidget(self.splitter, 1)
        outer.addWidget(self._build_log_panel())
        self.setCentralWidget(central)

    def _build_log_panel(self) -> QWidget:
        self.log_panel = QFrame()
        self.log_panel.setObjectName("logPanel")
        self.log_panel.setVisible(False)
        self.log_panel.setFixedHeight(150)
        self.log_panel.setStyleSheet(
            f"QFrame#logPanel{{background:{Color.SURFACE};border-top:1px solid {Color.BORDER};}}"
        )
        v = QVBoxLayout(self.log_panel)
        v.setContentsMargins(14, 8, 14, 10)
        v.setSpacing(6)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap("list", Color.TEXT_DIM, 14))
        t = QLabel("LOG")
        t.setProperty("class", "cardTitle")
        head.addWidget(ic)
        head.addWidget(t)
        head.addStretch(1)
        clear = QToolButton()
        clear.setIcon(icons.icon("x", Color.TEXT_DIM, 14))
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.setStyleSheet("QToolButton{border:none;background:transparent;}")
        clear.clicked.connect(lambda: self._log_view.clear())
        head.addWidget(clear)
        v.addLayout(head)
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setStyleSheet(
            f"QPlainTextEdit{{background:{Color.BG};border:1px solid {Color.BORDER_SOFT};"
            f"border-radius:8px;font-family:monospace;font-size:12px;padding:6px;}}"
        )
        v.addWidget(self._log_view, 1)
        return self.log_panel

    def _build_statusbar(self):
        sb = self.statusBar()
        self._status_icon = QLabel()
        self._status_icon.setPixmap(icons.pixmap("check", Color.SUCCESS, 14))
        self._status_text = QLabel("Pilih folder berisi SVG di kiri")
        self._status_text.setStyleSheet(f"color:{Color.TEXT_DIM};")
        sb.addWidget(self._status_icon)
        sb.addWidget(self._status_text)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setFixedWidth(160)
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{Color.SURFACE_2};border:1px solid {Color.BORDER};"
            f"border-radius:6px;height:10px;}}"
            f"QProgressBar::chunk{{background:{Color.ACCENT};border-radius:5px;}}"
        )
        sb.addPermanentWidget(self._progress)
        deps = QLabel("Inkscape · Ghostscript · ExifTool")
        deps.setStyleSheet(f"color:{Color.TEXT_FAINT};font-size:11px;")
        sb.addPermanentWidget(deps)

    # ---------- events ----------
    def _on_folder(self, folder: Path):
        self._current_folder = folder
        self.path_label.setText(str(folder))
        self.grid.load_folder(folder)
        n_svg = len(self.grid.all_files(SVG_EXT))
        self._set_status("check", Color.SUCCESS, f"{folder.name} — {n_svg} SVG")

    def _on_grid_selection(self, files: list[Path]):
        if not files:
            self.inspector.show_file(None, 0)
        else:
            self.inspector.show_file(files[0], len(files))

    def _on_thumb_size(self, size: int):
        self.grid.set_thumb_size(size)

    def _toggle_log(self):
        self.log_panel.setVisible(self.log_action.isChecked())

    # ---------- processing ----------
    def _target_svgs(self) -> list[Path]:
        """SVG terpilih; jika tak ada seleksi → semua SVG di folder."""
        sel = [p for p in self.grid.selected_files() if p.suffix.lower() in SVG_EXT]
        return sel or self.grid.all_files(SVG_EXT)

    def _process(self):
        svgs = self._target_svgs()
        if not svgs:
            self._set_status("alert", Color.WARNING, "Tidak ada SVG untuk diproses")
            return

        meta = self.inspector.metadata.get_metadata()
        ins = self.inspector
        settings = OutputSettings(
            out_dir=Path(ins.path_edit.text().strip() or "~/StockRanger/output"),
            output_mode=ins.mode_combo.currentData(),
            jpg_rule=ins.rule_combo.currentData(),
            jpg_value=ins.size_spin.value(),
            dpi=ins.dpi_spin.value(),
            jpg_quality=ins.q_spin.value(),
            jpg_mode=JpgMode.AUTO,
        )

        # Auto-pair JPG sibling (nama sama) di folder yang sama → mode manual.
        manual: dict[str, Path] = {}
        if self._current_folder:
            for svg in svgs:
                for ext in (".jpg", ".jpeg"):
                    cand = svg.with_suffix(ext)
                    if cand.exists():
                        manual[svg.stem] = cand
                        break
        if manual:
            settings.jpg_mode = JpgMode.MANUAL

        self.log_action.setChecked(True)
        self.log_panel.setVisible(True)
        self._set_processing(True)
        self._set_status("zap", Color.ACCENT, f"Memproses {len(svgs)} SVG…")
        self._log(f"▶ Mulai {len(svgs)} SVG · mode={settings.output_mode.value} · "
                  f"jpg={settings.jpg_rule.value}={settings.jpg_value}")

        self._worker = PipelineWorker(svgs, meta, settings, prefer_swop=False, manual_jpgs=manual)
        self._worker.logLine.connect(self._log)
        self._worker.progressed.connect(self._progress.setValue)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _set_processing(self, active: bool):
        self._progress.setVisible(active)
        self._progress.setValue(0)
        self.cta_btn.setEnabled(not active)
        self.inspector.process_btn.setEnabled(not active)

    def _on_done(self, ok: int, total: int):
        self._set_processing(False)
        if self._current_folder:
            self.grid.load_folder(self._current_folder)  # refresh thumbnail output baru
        if ok == total:
            self._set_status("check", Color.SUCCESS, f"Selesai — {ok}/{total} sukses")
            self._log(f"✓ Selesai — {ok}/{total} sukses")
        else:
            self._set_status("alert", Color.WARNING, f"Selesai dengan error — {ok}/{total}")
            self._log(f"⚠ Selesai — {ok}/{total} sukses (ada error)")

    # ---------- helpers ----------
    def _log(self, msg: str):
        color = Color.TEXT_DIM
        if "✓" in msg:
            color = Color.SUCCESS
        elif "✗" in msg or "error" in msg.lower() or "gagal" in msg.lower():
            color = Color.DANGER
        elif "⚠" in msg or "▶" in msg:
            color = Color.WARNING
        self._log_view.appendHtml(f"<span style='color:{color};'>{msg}</span>")
        self.statusBar().showMessage(msg, 4000)

    def _set_status(self, icon_name: str, color: str, text: str):
        self._status_icon.setPixmap(icons.pixmap(icon_name, color, 14))
        self._status_text.setText(text)
