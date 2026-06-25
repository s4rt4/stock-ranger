"""Card panels untuk area tengah: Preview, Metadata, Output."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core import templates
from ..core.models import Metadata
from . import icons
from .flowlayout import FlowLayout
from .theme import Color

MAX_TITLE = 200
MAX_DESC = 200
MAX_KEYWORDS = 50


class _ImageBox(QFrame):
    """Kotak preview yang menampilkan QPixmap (fit, jaga aspect) atau placeholder."""

    def __init__(self, caption: str, parent=None):
        super().__init__(parent)
        self._caption = caption
        self._pix: QPixmap | None = None
        self.setMinimumHeight(150)
        self.setStyleSheet(
            f"background:{Color.SURFACE_2};border:1px dashed {Color.BORDER};border-radius:10px;"
        )
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        self._label = QLabel(self._placeholder_html())
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("border:none;background:transparent;")
        v.addWidget(self._label)

    def _placeholder_html(self, text: str | None = None) -> str:
        return (
            f"<div style='color:{Color.TEXT_FAINT};font-size:12px;'>"
            f"{text or self._caption}</div>"
        )

    def set_pixmap(self, pix: QPixmap | None):
        self._pix = pix
        self._rescale()

    def set_text(self, text: str):
        self._pix = None
        self._label.setText(self._placeholder_html(text))

    def caption(self) -> str:
        return self._caption

    def _rescale(self):
        if self._pix is None:
            self._label.setText(self._placeholder_html())
            return
        area = self._label.size()
        scaled = self._pix.scaled(
            area, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._label.setPixmap(scaled)

    def resizeEvent(self, e):  # noqa: N802
        super().resizeEvent(e)
        self._rescale()


class PreviewCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(12)

        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap("image", Color.TEXT_DIM, 16))
        t = QLabel("PREVIEW")
        t.setProperty("class", "cardTitle")
        head.addWidget(ic)
        head.addWidget(t)
        head.addStretch(1)
        self.gamut = QLabel()
        self._set_gamut(0)
        head.addWidget(self.gamut)
        lay.addLayout(head)

        boxes = QHBoxLayout()
        boxes.setSpacing(12)
        self.rgb_box = _ImageBox("SVG (RGB)")
        self.cmyk_box = _ImageBox("CMYK (simulasi)")
        boxes.addWidget(self.rgb_box)
        boxes.addWidget(self.cmyk_box)
        lay.addLayout(boxes, 1)

    def set_loading(self):
        self.rgb_box.set_text("merender…")
        self.cmyk_box.set_text("merender…")
        self.gamut.setVisible(False)

    def set_images(self, rgb: QPixmap, cmyk: QPixmap):
        self.rgb_box.set_pixmap(rgb)
        self.cmyk_box.set_pixmap(cmyk)

    def clear(self):
        self.rgb_box.set_text("SVG (RGB)")
        self.cmyk_box.set_text("CMYK (simulasi)")
        self.gamut.setVisible(False)

    def set_gamut(self, n: int):
        self.gamut.setVisible(True)
        self._set_gamut(n)

    def _set_gamut(self, n: int):
        if n <= 0:
            self.gamut.setText("  ✓ Gamut OK  ")
            self.gamut.setStyleSheet(
                f"background:{Color.SURFACE_2};border:1px solid {Color.BORDER};"
                f"border-radius:10px;color:{Color.SUCCESS};padding:2px 8px;font-size:11px;"
            )
        else:
            self.gamut.setText(f"  ⚠ {n} warna out-of-gamut  ")
            self.gamut.setStyleSheet(
                f"background:{Color.SURFACE_2};border:1px solid {Color.WARNING};"
                f"border-radius:10px;color:{Color.WARNING};padding:2px 8px;font-size:11px;"
            )


class MetadataCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self._keywords: list[str] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)

        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap("tag", Color.TEXT_DIM, 16))
        t = QLabel("METADATA")
        t.setProperty("class", "cardTitle")
        head.addWidget(ic)
        head.addWidget(t)
        head.addStretch(1)

        # Template preset controls
        self.tpl_combo = QComboBox()
        self.tpl_combo.setMinimumWidth(90)
        self.tpl_combo.setToolTip("Muat metadata template")
        self.tpl_combo.activated.connect(self._load_selected_template)
        save_tpl = QToolButton()
        save_tpl.setIcon(icons.icon("download", Color.ICON, 16))
        save_tpl.setToolTip("Simpan metadata saat ini sebagai template")
        save_tpl.setCursor(Qt.CursorShape.PointingHandCursor)
        save_tpl.clicked.connect(self._save_template)
        del_tpl = QToolButton()
        del_tpl.setIcon(icons.icon("trash", Color.ICON, 16))
        del_tpl.setToolTip("Hapus template terpilih")
        del_tpl.setCursor(Qt.CursorShape.PointingHandCursor)
        del_tpl.clicked.connect(self._delete_template)
        for b in (save_tpl, del_tpl):
            b.setStyleSheet(
                f"QToolButton{{background:{Color.SURFACE_2};border:1px solid {Color.BORDER};"
                f"border-radius:7px;padding:5px;}}"
                f"QToolButton:hover{{border-color:{Color.ACCENT};}}"
            )
        head.addWidget(self.tpl_combo)
        head.addWidget(save_tpl)
        head.addWidget(del_tpl)
        lay.addLayout(head)

        # Title
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Judul artwork…")
        self.title_count = self._counter()
        self.title_edit.textChanged.connect(
            lambda s: self._update_count(self.title_count, len(s), MAX_TITLE)
        )
        lay.addLayout(self._labeled("Title", self.title_edit, self.title_count))

        # Description
        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setPlaceholderText("Deskripsi singkat…")
        self.desc_edit.setFixedHeight(60)
        self.desc_count = self._counter()
        self.desc_edit.textChanged.connect(
            lambda: self._update_count(
                self.desc_count, len(self.desc_edit.toPlainText()), MAX_DESC
            )
        )
        lay.addLayout(self._labeled("Description", self.desc_edit, self.desc_count))

        # Keywords
        self.kw_edit = QLineEdit()
        self.kw_edit.setPlaceholderText("Ketik keyword, tekan Enter atau koma…")
        self.kw_edit.returnPressed.connect(self._commit_keyword)
        self.kw_edit.textChanged.connect(self._on_kw_text)
        self.kw_count = self._counter()
        lay.addLayout(self._labeled("Keywords", self.kw_edit, self.kw_count))

        self._tag_host = QWidget()
        self._tag_flow = FlowLayout(self._tag_host, margin=0, spacing=6)
        lay.addWidget(self._tag_host)
        self._update_count(self.title_count, 0, MAX_TITLE)
        self._update_count(self.desc_count, 0, MAX_DESC)
        self._refresh_kw_count()

    def _labeled(self, label: str, widget: QWidget, counter: QLabel) -> QVBoxLayout:
        v = QVBoxLayout()
        v.setSpacing(4)
        row = QHBoxLayout()
        l = QLabel(label)
        l.setProperty("class", "hint")
        row.addWidget(l)
        row.addStretch(1)
        row.addWidget(counter)
        v.addLayout(row)
        v.addWidget(widget)
        return v

    def _counter(self) -> QLabel:
        c = QLabel()
        c.setProperty("class", "hint")
        c.setStyleSheet(f"color:{Color.TEXT_FAINT};font-size:11px;")
        return c

    def _update_count(self, label: QLabel, n: int, limit: int):
        label.setText(f"{n}/{limit}")
        label.setStyleSheet(
            f"font-size:11px;color:{Color.DANGER if n > limit else Color.TEXT_FAINT};"
        )

    def _on_kw_text(self, text: str):
        if text.endswith(","):
            self._commit_keyword()

    def _commit_keyword(self):
        raw = self.kw_edit.text().strip().strip(",").strip()
        self.kw_edit.clear()
        if not raw or raw.lower() in (k.lower() for k in self._keywords):
            return
        self._keywords.append(raw)
        self._add_tag_widget(raw)
        self._refresh_kw_count()

    def _add_tag_widget(self, text: str):
        chip = QFrame()
        h = QHBoxLayout(chip)
        h.setContentsMargins(9, 3, 5, 3)
        h.setSpacing(5)
        chip.setStyleSheet(
            f"QFrame{{background:{Color.ACCENT_SOFT};border:1px solid {Color.ACCENT};"
            f"border-radius:11px;}}"
        )
        lbl = QLabel(text)
        lbl.setStyleSheet("border:none;background:transparent;font-size:12px;")
        close = QToolButton()
        close.setIcon(icons.icon("x", Color.TEXT_DIM, 12))
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet("QToolButton{border:none;background:transparent;}")
        close.clicked.connect(lambda: self._remove_keyword(text, chip))
        h.addWidget(lbl)
        h.addWidget(close)
        self._tag_flow.addWidget(chip)

    def _remove_keyword(self, text: str, chip: QFrame):
        self._keywords = [k for k in self._keywords if k != text]
        chip.deleteLater()
        self._refresh_kw_count()

    def _refresh_kw_count(self):
        n = len(self._keywords)
        self.kw_count.setText(f"{n}/{MAX_KEYWORDS}")
        self.kw_count.setStyleSheet(
            f"font-size:11px;color:{Color.DANGER if n > MAX_KEYWORDS else Color.TEXT_FAINT};"
        )

    def keywords(self) -> list[str]:
        return list(self._keywords)

    # ---------- get/set metadata ----------
    def get_metadata(self) -> Metadata:
        return Metadata(
            title=self.title_edit.text().strip(),
            description=self.desc_edit.toPlainText().strip(),
            keywords=self.keywords(),
        )

    def set_metadata(self, meta: Metadata):
        self.title_edit.setText(meta.title)
        self.desc_edit.setPlainText(meta.description)
        # reset keyword chips
        self._keywords = []
        self._tag_flow.clear()
        for kw in meta.cleaned_keywords():
            self._keywords.append(kw)
            self._add_tag_widget(kw)
        self._refresh_kw_count()

    # ---------- templates ----------
    def refresh_templates(self, select: str | None = None):
        self.tpl_combo.blockSignals(True)
        self.tpl_combo.clear()
        self.tpl_combo.addItem("— Template —")
        names = templates.list_templates()
        self.tpl_combo.addItems(names)
        if select and select in names:
            self.tpl_combo.setCurrentText(select)
        self.tpl_combo.blockSignals(False)

    def _load_selected_template(self, index: int):
        if index <= 0:
            return
        name = self.tpl_combo.currentText()
        try:
            self.set_metadata(templates.load_template(name))
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Template", f"Gagal memuat: {e}")

    def _save_template(self):
        name, ok = QInputDialog.getText(self, "Simpan Template", "Nama template:")
        if not ok or not name.strip():
            return
        templates.save_template(name.strip(), self.get_metadata())
        self.refresh_templates(select=name.strip())

    def _delete_template(self):
        index = self.tpl_combo.currentIndex()
        if index <= 0:
            return
        name = self.tpl_combo.currentText()
        if QMessageBox.question(self, "Hapus Template", f"Hapus '{name}'?") == QMessageBox.StandardButton.Yes:
            templates.delete_template(name)
            self.refresh_templates()


class OutputCard(QFrame):
    processRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(12)

        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap("package", Color.TEXT_DIM, 16))
        t = QLabel("OUTPUT")
        t.setProperty("class", "cardTitle")
        head.addWidget(ic)
        head.addWidget(t)
        head.addStretch(1)
        lay.addLayout(head)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        self.w_spin = self._spin(64, 20000, 4000)
        self.h_spin = self._spin(64, 20000, 4000)
        self.dpi_spin = self._spin(72, 1200, 300)

        size_row = QHBoxLayout()
        size_row.setSpacing(6)
        size_row.addWidget(self.w_spin)
        x = QLabel("×")
        x.setProperty("class", "hint")
        size_row.addWidget(x)
        size_row.addWidget(self.h_spin)
        size_w = QWidget()
        size_w.setLayout(size_row)

        grid.addWidget(self._lbl("JPG Size (px)"), 0, 0)
        grid.addWidget(size_w, 1, 0)
        grid.addWidget(self._lbl("DPI"), 0, 1)
        grid.addWidget(self.dpi_spin, 1, 1)
        lay.addLayout(grid)

        lay.addWidget(self._lbl("Output Directory"))
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.path_edit = QLineEdit("~/StockRanger/output/")
        browse = QPushButton("Browse")
        browse.setIcon(icons.icon("folder", Color.ICON, 16))
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse)
        lay.addLayout(path_row)

        self.process_btn = QPushButton("  Process  •  ZIP")
        self.process_btn.setObjectName("primary")
        self.process_btn.setIcon(icons.icon("zap", "#08240f", 18))
        self.process_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.process_btn.setMinimumHeight(42)
        self.process_btn.clicked.connect(self.processRequested)
        lay.addWidget(self.process_btn)

    def _spin(self, lo: int, hi: int, val: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(val)
        s.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        return s

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setProperty("class", "hint")
        return l
