"""Panel kiri (folder tree) & tengah (content grid) ala Adobe Bridge."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QDir, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFileSystemModel, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QTreeView,
    QWidget,
)

from .thumbnails import SUPPORTED_EXT, ThumbnailLoader, render_thumbnail


class FolderTree(QTreeView):
    """Pohon folder filesystem (hanya direktori). Emit path saat dipilih."""

    folderSelected = pyqtSignal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("folderTree")
        self._model = QFileSystemModel(self)
        self._model.setRootPath("")
        self._model.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Drives)
        self.setModel(self._model)
        # sembunyikan kolom size/type/date — sisakan Name
        for col in (1, 2, 3):
            self.setColumnHidden(col, True)
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setIndentation(14)
        self.setUniformRowHeights(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self, index):
        path = self._model.filePath(index)
        if path:
            self.folderSelected.emit(Path(path))

    def reveal(self, path: Path):
        """Pilih & scroll ke folder tertentu (mis. Home saat start)."""
        idx = self._model.index(str(path))
        if idx.isValid():
            self.setCurrentIndex(idx)
            self.expand(idx)
            self.scrollTo(idx, QAbstractItemView.ScrollHint.PositionAtCenter)
            self.folderSelected.emit(path)


class ContentGrid(QListWidget):
    """Grid thumbnail file di folder terpilih (IconMode, multi-select)."""

    selectionChangedFiles = pyqtSignal(list)  # list[Path] terpilih
    activated2 = pyqtSignal(Path)             # double-click satu file

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("contentGrid")
        self._thumb = 150
        self._files: list[Path] = []
        self._loader: ThumbnailLoader | None = None

        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setWordWrap(True)
        self.setSpacing(10)
        self.setUniformItemSizes(True)
        self._apply_sizes()
        self.itemSelectionChanged.connect(self._emit_selection)
        self.itemDoubleClicked.connect(
            lambda it: self.activated2.emit(Path(it.data(Qt.ItemDataRole.UserRole)))
        )

    def _apply_sizes(self):
        self.setIconSize(QSize(self._thumb, self._thumb))
        self.setGridSize(QSize(self._thumb + 34, self._thumb + 46))

    def set_thumb_size(self, size: int):
        self._thumb = size
        self._apply_sizes()
        self.load_folder_files(self._files)  # re-render thumbnail

    # ---------- populate ----------
    def load_folder(self, folder: Path):
        try:
            files = sorted(
                (p for p in folder.iterdir()
                 if p.is_file() and p.suffix.lower() in SUPPORTED_EXT),
                key=lambda p: p.name.lower(),
            )
        except OSError:
            files = []
        self.load_folder_files(files)

    def load_folder_files(self, files: list[Path]):
        if self._loader:
            self._loader.stop()
            self._loader.wait(50)
        self._files = files
        self.clear()
        for p in files:
            it = QListWidgetItem(p.name)
            it.setData(Qt.ItemDataRole.UserRole, str(p))
            it.setSizeHint(QSize(self._thumb + 30, self._thumb + 44))
            it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self.addItem(it)
        if files:
            self._loader = ThumbnailLoader(files, self._thumb)
            self._loader.ready.connect(self._set_thumb)
            self._loader.start()

    def _set_thumb(self, row: int, pixmap):
        if 0 <= row < self.count():
            self.item(row).setIcon(QIcon(pixmap))

    def _emit_selection(self):
        self.selectionChangedFiles.emit(self.selected_files())

    # ---------- query ----------
    def selected_files(self) -> list[Path]:
        return [Path(it.data(Qt.ItemDataRole.UserRole)) for it in self.selectedItems()]

    def all_files(self, exts: set[str] | None = None) -> list[Path]:
        if exts is None:
            return list(self._files)
        return [p for p in self._files if p.suffix.lower() in exts]
