"""Panel kanan ala Bridge: File Properties + Metadata + Export settings."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.models import JpgSizeRule, OutputMode
from . import icons
from .panels import MetadataCard
from .theme import Color


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def file_properties(path: Path) -> dict[str, str]:
    """Properti ringkas untuk panel (dimensi, ukuran, tipe)."""
    props: dict[str, str] = {"Filename": path.name, "Type": path.suffix.lower().lstrip(".").upper()}
    try:
        props["File Size"] = _human_size(path.stat().st_size)
    except OSError:
        pass
    ext = path.suffix.lower()
    try:
        if ext in (".jpg", ".jpeg", ".png"):
            from PIL import Image
            with Image.open(path) as im:
                props["Dimensions"] = f"{im.width} × {im.height} px"
                props["Color Mode"] = im.mode
        elif ext == ".svg":
            from PyQt6.QtSvg import QSvgRenderer
            r = QSvgRenderer(str(path))
            if r.isValid():
                vb = r.viewBoxF()
                props["Dimensions"] = f"{vb.width():.0f} × {vb.height():.0f}"
            props["Color Mode"] = "Vector (RGB)"
    except Exception:
        pass
    return props


class Inspector(QTabWidget):
    """Tab: Metadata (props + editor) · Export (output settings)."""

    processRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("inspector")
        self.setMinimumWidth(330)
        self._build_metadata_tab()
        self._build_export_tab()

    # ---------- Metadata tab ----------
    def _build_metadata_tab(self):
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # File Properties (read-only)
        self.props_box = QFrame()
        self.props_box.setObjectName("propsBox")
        pv = QVBoxLayout(self.props_box)
        pv.setContentsMargins(14, 12, 14, 12)
        pv.setSpacing(6)
        head = QLabel("FILE PROPERTIES")
        head.setProperty("class", "cardTitle")
        pv.addWidget(head)
        self.props_form = QFormLayout()
        self.props_form.setHorizontalSpacing(12)
        self.props_form.setVerticalSpacing(4)
        self.props_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        pv.addLayout(self.props_form)
        self._set_props({"Filename": "— tidak ada file dipilih —"})

        self.metadata = MetadataCard()

        scroll = QScrollArea()
        inner = QWidget()
        iv = QVBoxLayout(inner)
        iv.setContentsMargins(12, 12, 12, 12)
        iv.setSpacing(12)
        iv.addWidget(self.props_box)
        iv.addWidget(self.metadata)
        iv.addStretch(1)
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        v.addWidget(scroll)
        self.addTab(wrap, "Metadata")

    def _set_props(self, props: dict[str, str]):
        while self.props_form.rowCount():
            self.props_form.removeRow(0)
        for k, val in props.items():
            key = QLabel(k)
            key.setStyleSheet(f"color:{Color.TEXT_FAINT};font-size:11px;")
            value = QLabel(val)
            value.setStyleSheet(f"color:{Color.TEXT};font-size:12px;")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.props_form.addRow(key, value)

    def show_file(self, path: Path | None, count: int = 0):
        if path is None:
            self._set_props({"Selection": f"{count} file dipilih" if count else "— kosong —"})
            return
        props = file_properties(path)
        if count > 1:
            props = {"Selection": f"{count} file", **props}
        self._set_props(props)

    # ---------- Export tab ----------
    def _build_export_tab(self):
        wrap = QWidget()
        outer = QVBoxLayout(wrap)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(12)

        # Output mode (Kel.1/2/3)
        outer.addWidget(self._lbl("Output Mode"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("EPS saja (+metadata)", OutputMode.EPS_ONLY)
        self.mode_combo.addItem("EPS + JPG (loose, nama sama)", OutputMode.PAIR_LOOSE)
        self.mode_combo.addItem("EPS + JPG di-ZIP per pasangan", OutputMode.PAIR_ZIP)
        self.mode_combo.setCurrentIndex(2)
        outer.addWidget(self.mode_combo)

        # JPG sizing (preserve aspect)
        outer.addWidget(self._lbl("Ukuran JPG (jaga aspect ratio)"))
        rule_row = QHBoxLayout()
        rule_row.setSpacing(8)
        self.rule_combo = QComboBox()
        self.rule_combo.addItem("Sisi terpanjang (px)", JpgSizeRule.LONGEST_SIDE)
        self.rule_combo.addItem("Maks megapixel (MP)", JpgSizeRule.MAX_MEGAPIXELS)
        self.rule_combo.currentIndexChanged.connect(self._on_rule_changed)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(100, 20000)
        self.size_spin.setValue(4000)
        self.size_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        rule_row.addWidget(self.rule_combo, 1)
        rule_row.addWidget(self.size_spin)
        outer.addLayout(rule_row)

        # DPI + Quality
        dq = QHBoxLayout()
        dq.setSpacing(10)
        dcol = QVBoxLayout()
        dcol.addWidget(self._lbl("DPI"))
        self.dpi_spin = self._spin(72, 1200, 300)
        dcol.addWidget(self.dpi_spin)
        qcol = QVBoxLayout()
        qcol.addWidget(self._lbl("JPG Quality"))
        self.q_spin = self._spin(50, 100, 92)
        qcol.addWidget(self.q_spin)
        dq.addLayout(dcol)
        dq.addLayout(qcol)
        outer.addLayout(dq)

        # Output dir
        outer.addWidget(self._lbl("Output Directory"))
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.path_edit = QLineEdit("~/StockRanger/output/")
        browse = QPushButton("Browse")
        browse.setIcon(icons.icon("folder", Color.ICON, 16))
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse)
        outer.addLayout(path_row)

        outer.addStretch(1)

        self.process_btn = QPushButton("  Process seleksi")
        self.process_btn.setObjectName("primary")
        self.process_btn.setIcon(icons.icon("zap", "#08240f", 18))
        self.process_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.process_btn.setMinimumHeight(42)
        self.process_btn.clicked.connect(self.processRequested)
        outer.addWidget(self.process_btn)

        self.addTab(wrap, "Export")

    def _on_rule_changed(self, _i):
        rule = self.rule_combo.currentData()
        if rule == JpgSizeRule.MAX_MEGAPIXELS:
            self.size_spin.setRange(1, 100)
            self.size_spin.setValue(16)
            self.size_spin.setSuffix(" MP")
        else:
            self.size_spin.setSuffix("")
            self.size_spin.setRange(100, 20000)
            self.size_spin.setValue(4000)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Pilih output directory", str(Path.home()))
        if d:
            self.path_edit.setText(d)

    def _spin(self, lo, hi, val):
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(val)
        s.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        return s

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setProperty("class", "hint")
        return l
