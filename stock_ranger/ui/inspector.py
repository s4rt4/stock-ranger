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

from ..core import targets as targets_store
from ..core.models import ExportTarget, JpgSizeRule, Metadata, OutputMode
from . import icons
from .panels import MetadataCard
from .theme import Color


class TargetRow(QFrame):
    """Satu baris preset microstock: checkbox + nama + mode + ukuran + hapus."""

    changed = pyqtSignal()
    deleted = pyqtSignal(object)

    def __init__(self, target: ExportTarget, parent=None):
        super().__init__(parent)
        self.setObjectName("targetRow")
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 10)
        v.setSpacing(7)

        from PyQt6.QtWidgets import QCheckBox, QToolButton
        top = QHBoxLayout()
        top.setSpacing(7)
        self.chk = QCheckBox()
        self.chk.setChecked(target.enabled)
        self.chk.toggled.connect(self.changed)
        self.name = QLineEdit(target.name)
        self.name.setPlaceholderText("Nama microstock…")
        self.name.textChanged.connect(self.changed)
        trash = QToolButton()
        trash.setIcon(icons.icon("trash", Color.TEXT_DIM, 15))
        trash.setCursor(Qt.CursorShape.PointingHandCursor)
        trash.setStyleSheet("QToolButton{border:none;background:transparent;}")
        trash.clicked.connect(lambda: self.deleted.emit(self))
        top.addWidget(self.chk)
        top.addWidget(self.name, 1)
        top.addWidget(trash)
        v.addLayout(top)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.mode = QComboBox()
        self.mode.addItem("EPS", OutputMode.EPS_ONLY)
        self.mode.addItem("EPS+JPG", OutputMode.PAIR_LOOSE)
        self.mode.addItem("ZIP pair", OutputMode.PAIR_ZIP)
        self.mode.setCurrentIndex([OutputMode.EPS_ONLY, OutputMode.PAIR_LOOSE,
                                   OutputMode.PAIR_ZIP].index(target.output_mode))
        self.mode.currentIndexChanged.connect(self.changed)
        self.rule = QComboBox()
        self.rule.addItem("px", JpgSizeRule.LONGEST_SIDE)
        self.rule.addItem("MP", JpgSizeRule.MAX_MEGAPIXELS)
        self.rule.setCurrentIndex(0 if target.jpg_rule == JpgSizeRule.LONGEST_SIDE else 1)
        self.rule.currentIndexChanged.connect(self.changed)
        self.val = QSpinBox()
        self.val.setRange(1, 20000)
        self.val.setValue(target.jpg_value)
        self.val.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.val.valueChanged.connect(self.changed)
        row.addWidget(self.mode, 2)
        row.addWidget(self.val, 1)
        row.addWidget(self.rule)
        v.addLayout(row)

    def to_target(self) -> ExportTarget:
        return ExportTarget(
            name=self.name.text().strip() or "Target",
            output_mode=self.mode.currentData(),
            jpg_rule=self.rule.currentData(),
            jpg_value=self.val.value(),
            enabled=self.chk.isChecked(),
        )


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
        wrap.setStyleSheet(f"background:{Color.SURFACE};")
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
        inner.setStyleSheet(f"background:{Color.SURFACE};")
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea{{background:{Color.SURFACE};border:none;}}")
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
            value.setWordWrap(True)  # nama file panjang membungkus, tidak terpotong
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.props_form.addRow(key, value)

    def show_file(self, path: Path | None, count: int = 0):
        if path is None:
            # Deselect → properties & editor metadata dikosongkan
            self._set_props({"Selection": "— tidak ada file dipilih —"})
            self.metadata.set_metadata(Metadata())
            return
        props = file_properties(path)
        if count > 1:
            # Multi-select: pertahankan editor (untuk metadata batch yang sama)
            self._set_props({"Selection": f"{count} file", **props})
            return
        self._set_props(props)
        # Single select → tampilkan metadata file itu (kosong bila tak punya)
        from ..core import metadata_writer
        self.metadata.set_metadata(metadata_writer.read_metadata(path))

    # ---------- Export tab ----------
    def _build_export_tab(self):
        from PyQt6.QtWidgets import QToolButton

        wrap = QWidget()
        wrap.setStyleSheet(f"background:{Color.SURFACE};")
        outer = QVBoxLayout(wrap)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        # Header target + tombol tambah
        head = QHBoxLayout()
        h = self._lbl("EXPORT TARGETS")
        h.setProperty("class", "cardTitle")
        head.addWidget(h)
        head.addStretch(1)
        add = QToolButton()
        add.setIcon(icons.icon("add", Color.ICON, 16))
        add.setToolTip("Tambah target")
        add.setCursor(Qt.CursorShape.PointingHandCursor)
        add.setStyleSheet(
            f"QToolButton{{background:{Color.SURFACE_2};border:1px solid {Color.BORDER};"
            f"border-radius:7px;padding:4px;}}QToolButton:hover{{border-color:{Color.ACCENT};}}"
        )
        add.clicked.connect(self._add_target)
        head.addWidget(add)
        outer.addLayout(head)

        # Daftar target (scroll)
        self._rows: list[TargetRow] = []
        self._rows_host = QWidget()
        self._rows_host.setStyleSheet(f"background:{Color.SURFACE};")
        self._rows_lay = QVBoxLayout(self._rows_host)
        self._rows_lay.setContentsMargins(0, 0, 0, 0)
        self._rows_lay.setSpacing(8)
        self._rows_lay.addStretch(1)
        rows_scroll = QScrollArea()
        rows_scroll.setWidget(self._rows_host)
        rows_scroll.setWidgetResizable(True)
        rows_scroll.setFrameShape(QFrame.Shape.NoFrame)
        rows_scroll.setStyleSheet(f"QScrollArea{{background:{Color.SURFACE};border:none;}}")
        rows_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(rows_scroll, 1)
        for t in targets_store.load_targets():
            self._append_row(t)

        # DPI + Output dir
        dq = QHBoxLayout()
        dq.setSpacing(10)
        dcol = QVBoxLayout()
        dcol.addWidget(self._lbl("DPI"))
        self.dpi_spin = self._spin(72, 1200, 300)
        dcol.addWidget(self.dpi_spin)
        dq.addLayout(dcol)
        dq.addStretch(1)
        outer.addLayout(dq)

        outer.addWidget(self._lbl("Output Directory (base)"))
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

        self.process_btn = QPushButton("  Process → target aktif")
        self.process_btn.setObjectName("primary")
        self.process_btn.setIcon(icons.icon("zap", "#08240f", 18))
        self.process_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.process_btn.setMinimumHeight(42)
        self.process_btn.clicked.connect(self.processRequested)
        outer.addWidget(self.process_btn)

        self.addTab(wrap, "Export")

    def _append_row(self, target: ExportTarget):
        row = TargetRow(target)
        row.changed.connect(self._persist_targets)
        row.deleted.connect(self._remove_row)
        self._rows.append(row)
        self._rows_lay.insertWidget(self._rows_lay.count() - 1, row)

    def _add_target(self):
        self._append_row(ExportTarget("Microstock baru", OutputMode.PAIR_ZIP))
        self._persist_targets()

    def _remove_row(self, row: TargetRow):
        if row in self._rows:
            self._rows.remove(row)
            row.deleteLater()
            self._persist_targets()

    def get_targets(self) -> list[ExportTarget]:
        return [r.to_target() for r in self._rows]

    def _persist_targets(self):
        targets_store.save_targets(self.get_targets())

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
