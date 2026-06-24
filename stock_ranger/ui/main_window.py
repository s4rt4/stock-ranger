"""MainWindow — toolbar atas, collapsible sidebar, area tengah, log panel, statusbar.

Fase 2: drag&drop, live preview + gamut, metadata template, manual JPG import,
log panel.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction, QPixmap
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core import profile_manager
from ..core.models import JpgMode, Metadata, OutputSettings
from . import icons
from .panels import MetadataCard, OutputCard, PreviewCard
from .preview_worker import PreviewWorker
from .sidebar import Sidebar
from .theme import Color, stylesheet
from .worker import PipelineWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stock Ranger")
        self.resize(1200, 840)
        self.setMinimumSize(900, 560)
        self.setStyleSheet(stylesheet())
        self.setAcceptDrops(True)

        self._manual_jpgs: dict[str, Path] = {}
        self._preview_path: str | None = None
        self._preview_worker: PreviewWorker | None = None
        self._worker: PipelineWorker | None = None

        self._build_toolbar()
        self._build_body()
        self._build_statusbar()

        self.metadata.refresh_templates()
        self.sidebar.queue.currentItemChanged.connect(self._on_queue_selection)
        self.sidebar.profile_combo.currentIndexChanged.connect(self._reload_preview)

    # ---------- toolbar ----------
    def _build_toolbar(self):
        tb = QToolBar()
        tb.setObjectName("topbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        self.menu_action = QAction(icons.icon("menu", Color.ICON, 20), "Toggle sidebar", self)
        self.menu_action.triggered.connect(self._toggle_sidebar)
        tb.addAction(self.menu_action)

        brand = QWidget()
        bl = QHBoxLayout(brand)
        bl.setContentsMargins(8, 0, 8, 0)
        bl.setSpacing(2)
        name = QLabel("Stock Ranger")
        name.setObjectName("brand")
        dot = QLabel("●")
        dot.setObjectName("brandDot")
        bl.addWidget(name)
        bl.addWidget(dot)
        tb.addWidget(brand)
        tb.addWidget(self._vsep())

        self._add_tool(tb, "file-plus", "Add SVG", self._add_files)
        self._add_tool(tb, "image-import", "Import JPG (mode manual)", self._import_jpgs)
        self._add_tool(tb, "trash", "Remove selected", self._remove_files)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self.log_action = self._add_tool(tb, "list", "Toggle log panel", self._toggle_log, checkable=True)
        self._add_tool(tb, "settings", "Settings", None)
        self._add_tool(tb, "info", "About", None)
        tb.addWidget(self._vsep())

        cta = QWidget()
        cl = QHBoxLayout(cta)
        cl.setContentsMargins(2, 0, 2, 0)
        self.cta_btn = QToolButton()
        self.cta_btn.setObjectName("cta")
        self.cta_btn.setText("  Process  •  ZIP")
        self.cta_btn.setIcon(icons.icon("zap", "#08240f", 18))
        self.cta_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.cta_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cta_btn.clicked.connect(self._process)
        cl.addWidget(self.cta_btn)
        tb.addWidget(cta)

    def _add_tool(self, tb: QToolBar, icon_name: str, tip: str, slot, checkable=False):
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
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.addRequested.connect(self._add_files)
        self.sidebar.removeRequested.connect(self._remove_files)
        h.addWidget(self.sidebar)

        content = QWidget()
        cv = QVBoxLayout(content)
        cv.setContentsMargins(18, 18, 18, 18)
        cv.setSpacing(16)

        self.preview = PreviewCard()
        self.metadata = MetadataCard()
        self.output = OutputCard()
        self.output.processRequested.connect(self._process)

        cv.addWidget(self.preview)
        cv.addWidget(self.metadata)
        cv.addWidget(self.output)
        cv.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent;} "
            "QScrollArea > QWidget > QWidget{background:transparent;}"
        )

        # Kolom kanan: konten (atas) + log panel (bawah, collapsible)
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)
        rv.addWidget(scroll, 1)
        rv.addWidget(self._build_log_panel())
        h.addWidget(right, 1)

        self.setCentralWidget(central)

    def _build_log_panel(self) -> QWidget:
        self.log_panel = QFrame()
        self.log_panel.setObjectName("logPanel")
        self.log_panel.setVisible(False)
        self.log_panel.setFixedHeight(170)
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
        clear.setToolTip("Bersihkan log")
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
        self._status_text = QLabel("Ready — 0 file di queue")
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

    # ---------- drag & drop ----------
    def _svgs_in(self, mime) -> list[str]:
        if not mime.hasUrls():
            return []
        return [
            u.toLocalFile()
            for u in mime.urls()
            if u.toLocalFile().lower().endswith(".svg")
        ]

    def dragEnterEvent(self, e):  # noqa: N802
        if self._svgs_in(e.mimeData()):
            e.acceptProposedAction()

    def dropEvent(self, e):  # noqa: N802
        svgs = self._svgs_in(e.mimeData())
        for p in svgs:
            self.sidebar.add_file(Path(p).name, p)
        if svgs:
            self._update_status()
            self._log(f"Drag & drop: {len(svgs)} SVG ditambahkan")
            e.acceptProposedAction()

    # ---------- actions ----------
    def _toggle_sidebar(self):
        self.sidebar.toggle()

    def _toggle_log(self):
        self.log_panel.setVisible(self.log_action.isChecked())

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Pilih file SVG", str(Path.home()), "SVG files (*.svg)"
        )
        for p in paths:
            self.sidebar.add_file(Path(p).name, p)
        if paths:
            self._update_status()
            self._log(f"Ditambahkan {len(paths)} SVG ke queue")

    def _import_jpgs(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Pilih JPG untuk dipasangkan", str(Path.home()), "JPEG (*.jpg *.jpeg)"
        )
        if not paths:
            return
        svg_stems = {Path(p).stem for p in self.sidebar.file_paths()}
        matched = 0
        for p in paths:
            stem = Path(p).stem
            if stem in svg_stems:
                self._manual_jpgs[stem] = Path(p)
                matched += 1
        self.sidebar.jpgmode_combo.setCurrentIndex(1)  # aktifkan mode manual
        self._log(f"Import JPG: {matched}/{len(paths)} cocok dengan SVG di queue")
        missing = sorted(svg_stems - set(self._manual_jpgs))
        if missing:
            self._log(
                f"⚠ {len(missing)} SVG belum berpasangan JPG: "
                f"{', '.join(missing[:6])}{'…' if len(missing) > 6 else ''}"
            )

    def _remove_files(self):
        for item in self.sidebar.queue.selectedItems():
            stem = Path(item.data(Qt.ItemDataRole.UserRole) or "").stem
            self._manual_jpgs.pop(stem, None)
            self.sidebar.queue.takeItem(self.sidebar.queue.row(item))
        self._update_status()

    # ---------- live preview ----------
    def _on_queue_selection(self, current, _previous):
        if current is None:
            self.preview.clear()
            self._preview_path = None
            return
        path = current.data(Qt.ItemDataRole.UserRole)
        if path:
            self._start_preview(Path(path))

    def _reload_preview(self):
        if self._preview_path:
            self._start_preview(Path(self._preview_path))

    def _start_preview(self, svg: Path):
        self.preview.set_loading()
        self._preview_path = str(svg)
        prefer_swop = self.sidebar.profile_combo.currentIndex() == 0
        icc = profile_manager.resolve_profile(prefer_swop)  # tidak men-download
        self._preview_worker = PreviewWorker(svg, icc)
        self._preview_worker.ready.connect(self._on_preview_ready)
        self._preview_worker.failed.connect(self._on_preview_failed)
        self._preview_worker.start()

    def _on_preview_ready(self, rgb_qimg, cmyk_qimg, gamut: int, path: str):
        if path != self._preview_path:
            return  # hasil basi (user sudah pindah file)
        self.preview.set_images(QPixmap.fromImage(rgb_qimg), QPixmap.fromImage(cmyk_qimg))
        self.preview.set_gamut(gamut)

    def _on_preview_failed(self, err: str, path: str):
        if path != self._preview_path:
            return
        self.preview.rgb_box.set_text("preview gagal")
        self.preview.cmyk_box.set_text(err[:48])

    # ---------- processing ----------
    def _process(self):
        paths = [Path(p) for p in self.sidebar.file_paths()]
        if not paths:
            self._set_status("alert", Color.WARNING, "Queue kosong — tambahkan SVG dulu")
            return

        meta = self.metadata.get_metadata()
        settings = OutputSettings(
            out_dir=Path(self.output.path_edit.text().strip() or "~/StockRanger/output"),
            jpg_width=self.output.w_spin.value(),
            jpg_height=self.output.h_spin.value(),
            dpi=self.output.dpi_spin.value(),
            jpg_mode=(
                JpgMode.AUTO
                if self.sidebar.jpgmode_combo.currentIndex() == 0
                else JpgMode.MANUAL
            ),
        )
        prefer_swop = self.sidebar.profile_combo.currentIndex() == 0

        self.log_action.setChecked(True)
        self.log_panel.setVisible(True)
        self._set_processing(True)
        self._set_status("zap", Color.ACCENT, f"Memproses {len(paths)} file…")
        self._log(f"▶ Mulai memproses {len(paths)} file…")

        self._worker = PipelineWorker(paths, meta, settings, prefer_swop, dict(self._manual_jpgs))
        self._worker.logLine.connect(self._log)
        self._worker.progressed.connect(self._progress.setValue)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _set_processing(self, active: bool):
        self._progress.setVisible(active)
        self._progress.setValue(0)
        self.cta_btn.setEnabled(not active)
        self.output.process_btn.setEnabled(not active)

    def _on_done(self, ok: int, total: int):
        self._set_processing(False)
        if ok == total:
            self._set_status("check", Color.SUCCESS, f"Selesai — {ok}/{total} file → ZIP siap upload")
            self._log(f"✓ Selesai — {ok}/{total} sukses")
        else:
            self._set_status("alert", Color.WARNING, f"Selesai dengan error — {ok}/{total} sukses")
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

    def _update_status(self):
        n = self.sidebar.queue.count()
        self._set_status("check", Color.SUCCESS, f"Ready — {n} file di queue")

    def _set_status(self, icon_name: str, color: str, text: str):
        self._status_icon.setPixmap(icons.pixmap(icon_name, color, 14))
        self._status_text.setText(text)
