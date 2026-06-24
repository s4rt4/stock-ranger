"""MainWindow — merakit toolbar atas, collapsible sidebar, area tengah, statusbar."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core.models import JpgMode, Metadata, OutputSettings
from . import icons
from .panels import MetadataCard, OutputCard, PreviewCard
from .sidebar import Sidebar
from .theme import Color, stylesheet
from .worker import PipelineWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stock Ranger")
        self.resize(1200, 820)
        self.setMinimumSize(900, 560)
        self.setStyleSheet(stylesheet())

        self._build_toolbar()
        self._build_body()
        self._build_statusbar()

    # ---------- toolbar ----------
    def _build_toolbar(self):
        tb = QToolBar()
        tb.setObjectName("topbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        # Sidebar toggle
        self.menu_action = QAction(icons.icon("menu", Color.ICON, 20), "Toggle sidebar", self)
        self.menu_action.triggered.connect(self._toggle_sidebar)
        tb.addAction(self.menu_action)

        # Brand
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

        # Primary actions
        self._add_tool(tb, "file-plus", "Add SVG", self._add_files)
        self._add_tool(tb, "trash", "Remove selected", self._remove_files)
        self._add_tool(tb, "layers", "Batch queue", None, checkable=True)

        # Spacer mendorong sisi kanan
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self._add_tool(tb, "settings", "Settings", None)
        self._add_tool(tb, "info", "About", None)
        tb.addWidget(self._vsep())

        # CTA: Process & ZIP
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

        # Scroll area supaya card memakai tinggi natural & tidak saling tumpang tindih
        scroll = QScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;} QScrollArea > QWidget > QWidget{background:transparent;}")
        h.addWidget(scroll, 1)

        self.setCentralWidget(central)

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

    # ---------- actions ----------
    def _toggle_sidebar(self):
        self.sidebar.toggle()

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Pilih file SVG", str(Path.home()), "SVG files (*.svg)"
        )
        for p in paths:
            self.sidebar.add_file(Path(p).name, p)
        self._update_status()

    def _remove_files(self):
        for item in self.sidebar.queue.selectedItems():
            self.sidebar.queue.takeItem(self.sidebar.queue.row(item))
        self._update_status()

    def _process(self):
        paths = [Path(p) for p in self.sidebar.file_paths()]
        if not paths:
            self._set_status("alert", Color.WARNING, "Queue kosong — tambahkan SVG dulu")
            return

        meta = Metadata(
            title=self.metadata.title_edit.text().strip(),
            description=self.metadata.desc_edit.toPlainText().strip(),
            keywords=self.metadata.keywords(),
        )
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

        self._set_processing(True)
        self._set_status("zap", Color.ACCENT, f"Memproses {len(paths)} file…")
        self._worker = PipelineWorker(paths, meta, settings, prefer_swop)
        self._worker.logLine.connect(lambda m: self.statusBar().showMessage(m, 4000))
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
        else:
            self._set_status("alert", Color.WARNING, f"Selesai dengan error — {ok}/{total} sukses")

    def _update_status(self):
        n = self.sidebar.queue.count()
        self._set_status("check", Color.SUCCESS, f"Ready — {n} file di queue")

    def _set_status(self, icon_name: str, color: str, text: str):
        self._status_icon.setPixmap(icons.pixmap(icon_name, color, 14))
        self._status_text.setText(text)
