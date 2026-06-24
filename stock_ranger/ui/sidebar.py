"""Collapsible sidebar — file queue + settings, dengan animasi lebar.

Expanded: menampilkan label section, daftar file, dan settings.
Collapsed: menyusut jadi rail tipis berisi icon-only buttons.
"""

from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import icons
from .theme import Color

EXPANDED_W = 258
COLLAPSED_W = 58


def _tool_btn(name: str, tooltip: str, size: int = 20) -> QToolButton:
    b = QToolButton()
    b.setIcon(icons.icon(name, Color.ICON, size))
    b.setIconSize(b.iconSize().__class__(size, size))
    b.setToolTip(tooltip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


class Sidebar(QWidget):
    addRequested = pyqtSignal()
    removeRequested = pyqtSignal()
    toggled = pyqtSignal(bool)  # True = expanded

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self._expanded = True
        self.setFixedWidth(EXPANDED_W)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header dengan tombol collapse
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 12, 10, 8)
        self._title = QLabel("Workspace")
        self._title.setProperty("class", "section")
        self.collapse_btn = QToolButton()
        self.collapse_btn.setObjectName("collapseBtn")
        self.collapse_btn.setIcon(icons.icon("chevrons-left", Color.ICON, 18))
        self.collapse_btn.setToolTip("Collapse sidebar")
        self.collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.collapse_btn.clicked.connect(self.toggle)
        hl.addWidget(self._title)
        hl.addStretch(1)
        hl.addWidget(self.collapse_btn)
        root.addWidget(header)

        # Stacked: page 0 = expanded, page 1 = collapsed rail
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_expanded())
        self._stack.addWidget(self._build_rail())
        root.addWidget(self._stack, 1)

        self._anim = QPropertyAnimation(self, b"maximumWidth")
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim2 = QPropertyAnimation(self, b"minimumWidth")
        self._anim2.setDuration(180)
        self._anim2.setEasingCurve(QEasingCurve.Type.InOutCubic)

    # ---------- expanded content ----------
    def _build_expanded(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 0, 12, 12)
        lay.setSpacing(8)

        lbl = QLabel("FILE QUEUE")
        lbl.setProperty("class", "section")
        lay.addWidget(lbl)

        self.queue = QListWidget()
        self.queue.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(self.queue, 1)

        # Add / Remove row
        row = QHBoxLayout()
        row.setSpacing(8)
        self.add_btn = QToolButton()
        self.add_btn.setIcon(icons.icon("file-plus", Color.ICON, 18))
        self.add_btn.setText("  Add SVG")
        self.add_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setStyleSheet(
            f"QToolButton{{background:{Color.SURFACE_2};border:1px solid {Color.BORDER};"
            f"border-radius:8px;padding:8px 12px;}}"
            f"QToolButton:hover{{border-color:{Color.ACCENT};background:{Color.SURFACE_3};}}"
        )
        self.add_btn.clicked.connect(self.addRequested)
        self.remove_btn = _tool_btn("trash", "Remove selected", 18)
        self.remove_btn.setStyleSheet(
            f"QToolButton{{background:{Color.SURFACE_2};border:1px solid {Color.BORDER};"
            f"border-radius:8px;padding:8px;}}"
            f"QToolButton:hover{{border-color:{Color.DANGER};background:{Color.SURFACE_3};}}"
        )
        self.remove_btn.clicked.connect(self.removeRequested)
        row.addWidget(self.add_btn, 1)
        row.addWidget(self.remove_btn)
        lay.addLayout(row)

        # Settings section
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{Color.BORDER_SOFT};")
        lay.addWidget(sep)

        slbl = QLabel("SETTINGS")
        slbl.setProperty("class", "section")
        lay.addWidget(slbl)

        lay.addWidget(self._field("ICC Profile"))
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(["US Web Coated SWOP v2", "Ghostscript default (CMYK)"])
        lay.addWidget(self.profile_combo)

        lay.addWidget(self._field("JPG Mode"))
        self.jpgmode_combo = QComboBox()
        self.jpgmode_combo.addItems(["Auto (rasterize SVG)", "Manual import"])
        lay.addWidget(self.jpgmode_combo)

        return w

    def _field(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setProperty("class", "hint")
        return l

    # ---------- collapsed rail ----------
    def _build_rail(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(9, 4, 9, 12)
        lay.setSpacing(8)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        add = _tool_btn("file-plus", "Add SVG", 20)
        add.clicked.connect(self.addRequested)
        rem = _tool_btn("trash", "Remove selected", 20)
        rem.clicked.connect(self.removeRequested)
        for b in (add, rem):
            b.setStyleSheet(
                f"QToolButton{{background:{Color.SURFACE_2};border:1px solid {Color.BORDER};"
                f"border-radius:9px;padding:9px;}}"
                f"QToolButton:hover{{border-color:{Color.ACCENT};background:{Color.SURFACE_3};}}"
            )
            lay.addWidget(b)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{Color.BORDER_SOFT};")
        lay.addWidget(sep)

        for nm, tip in (("droplet", "ICC Profile"), ("image", "JPG Mode"), ("layers", "Batch")):
            b = _tool_btn(nm, tip, 20)
            b.setStyleSheet(
                f"QToolButton{{background:transparent;border:1px solid transparent;"
                f"border-radius:9px;padding:9px;}}"
                f"QToolButton:hover{{background:{Color.SURFACE_3};border-color:{Color.BORDER};}}"
            )
            lay.addWidget(b)

        lay.addStretch(1)
        return w

    # ---------- collapse logic ----------
    def toggle(self):
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool):
        if expanded == self._expanded:
            return
        self._expanded = expanded
        target = EXPANDED_W if expanded else COLLAPSED_W
        self._stack.setCurrentIndex(0 if expanded else 1)
        self.collapse_btn.setIcon(
            icons.icon("chevrons-left" if expanded else "chevrons-right", Color.ICON, 18)
        )
        self.collapse_btn.setToolTip("Collapse sidebar" if expanded else "Expand sidebar")
        self._title.setVisible(expanded)

        for anim, prop in ((self._anim, b"maximumWidth"), (self._anim2, b"minimumWidth")):
            anim.stop()
            anim.setStartValue(self.width())
            anim.setEndValue(target)
            anim.start()
        self.toggled.emit(expanded)

    def is_expanded(self) -> bool:
        return self._expanded

    def add_file(self, name: str, path: str | None = None):
        item = QListWidgetItem(icons.icon("file", Color.ICON, 16), "  " + name)
        if path is not None:
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
        self.queue.addItem(item)

    def file_paths(self) -> list[str]:
        out: list[str] = []
        for i in range(self.queue.count()):
            data = self.queue.item(i).data(Qt.ItemDataRole.UserRole)
            if data:
                out.append(data)
        return out
