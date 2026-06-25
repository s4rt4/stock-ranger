"""Tema gelap modern — color tokens + QSS global.

Token warna dipakai juga oleh icon system supaya icon & UI konsisten.
Palet: dark slate dengan aksen indigo, dan hijau untuk CTA Process.
"""

from __future__ import annotations


class Color:
    # Surfaces (gelap -> terang)
    BG = "#15171c"            # window background paling dasar
    SURFACE = "#1b1e24"       # panel
    SURFACE_2 = "#22262e"     # panel elevated / list item
    SURFACE_3 = "#2a2f39"     # hover
    BORDER = "#2e333d"
    BORDER_SOFT = "#262b33"

    # Teks
    TEXT = "#e6e9ef"
    TEXT_DIM = "#9aa3b2"
    TEXT_FAINT = "#646c7c"

    # Aksen
    ACCENT = "#6366f1"        # indigo
    ACCENT_HOVER = "#7c7ff6"
    ACCENT_SOFT = "#2a2d52"
    SUCCESS = "#22c55e"
    SUCCESS_HOVER = "#34d36b"
    WARNING = "#f5a623"
    DANGER = "#ef4444"

    # Icon states
    ICON = "#aab2c0"
    ICON_HOVER = "#e6e9ef"
    ICON_ACTIVE = "#ffffff"


def stylesheet() -> str:
    c = Color
    return f"""
    * {{
        font-family: "Inter", "Segoe UI", "Noto Sans", sans-serif;
        font-size: 13px;
        color: {c.TEXT};
        outline: none;
    }}
    QMainWindow, QWidget#root {{ background: {c.BG}; }}

    /* ---------- Toolbar ---------- */
    QToolBar#topbar {{
        background: {c.SURFACE};
        border: none;
        border-bottom: 1px solid {c.BORDER};
        padding: 6px 10px;
        spacing: 4px;
    }}
    QToolBar#topbar QToolButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 7px;
        margin: 0 1px;
    }}
    QToolBar#topbar QToolButton:hover {{
        background: {c.SURFACE_3};
        border-color: {c.BORDER};
    }}
    QToolBar#topbar QToolButton:pressed {{ background: {c.SURFACE_2}; }}
    QToolBar#topbar QToolButton:checked {{
        background: {c.ACCENT_SOFT};
        border-color: {c.ACCENT};
    }}
    QToolBar#topbar QToolButton#cta {{
        background: {c.SUCCESS};
        color: #08240f;
        font-weight: 600;
        padding: 7px 14px;
    }}
    QToolBar#topbar QToolButton#cta:hover {{ background: {c.SUCCESS_HOVER}; }}

    QLabel#brand {{ font-size: 15px; font-weight: 700; color: {c.TEXT}; }}
    QLabel#brandDot {{ color: {c.ACCENT}; font-size: 15px; font-weight: 700; }}
    QFrame#vsep {{ background: {c.BORDER}; max-width: 1px; min-width: 1px; }}

    /* ---------- Sidebar ---------- */
    QWidget#sidebar {{
        background: {c.SURFACE};
        border-right: 1px solid {c.BORDER};
    }}
    QWidget#sidebar QLabel.section {{
        color: {c.TEXT_FAINT};
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
        padding: 4px 2px;
    }}
    QToolButton#collapseBtn {{
        background: transparent; border: 1px solid transparent; border-radius: 7px; padding: 6px;
    }}
    QToolButton#collapseBtn:hover {{ background: {c.SURFACE_3}; border-color: {c.BORDER}; }}

    /* ---------- File queue list ---------- */
    QListWidget {{
        background: {c.SURFACE_2};
        border: 1px solid {c.BORDER_SOFT};
        border-radius: 10px;
        padding: 4px;
    }}
    QListWidget::item {{
        padding: 8px 10px;
        border-radius: 7px;
        margin: 1px 0;
        color: {c.TEXT};
    }}
    QListWidget::item:hover {{ background: {c.SURFACE_3}; }}
    QListWidget::item:selected {{ background: {c.ACCENT_SOFT}; color: {c.TEXT}; }}

    /* ---------- Cards / panels ---------- */
    QFrame.card {{
        background: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: 12px;
    }}
    QLabel.cardTitle {{ font-size: 12px; font-weight: 700; color: {c.TEXT_DIM}; letter-spacing: .5px; }}
    QLabel.hint {{ color: {c.TEXT_FAINT}; font-size: 12px; }}

    /* ---------- Inputs ---------- */
    QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {{
        background: {c.SURFACE_2};
        border: 1px solid {c.BORDER};
        border-radius: 8px;
        padding: 7px 10px;
        selection-background-color: {c.ACCENT};
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
        border-color: {c.ACCENT};
    }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{
        background: {c.SURFACE_2};
        border: 1px solid {c.BORDER};
        border-radius: 8px;
        selection-background-color: {c.ACCENT_SOFT};
        padding: 4px;
    }}

    /* ---------- Buttons ---------- */
    QPushButton {{
        background: {c.SURFACE_2};
        border: 1px solid {c.BORDER};
        border-radius: 8px;
        padding: 8px 14px;
        color: {c.TEXT};
    }}
    QPushButton:hover {{ background: {c.SURFACE_3}; border-color: {c.ACCENT}; }}
    QPushButton:pressed {{ background: {c.SURFACE}; }}
    QPushButton#primary {{
        background: {c.SUCCESS}; border: none; color: #08240f; font-weight: 600;
    }}
    QPushButton#primary:hover {{ background: {c.SUCCESS_HOVER}; }}

    /* ---------- Keyword tags ---------- */
    QLabel.kwTag {{
        background: {c.ACCENT_SOFT};
        border: 1px solid {c.ACCENT};
        border-radius: 11px;
        padding: 3px 9px;
        color: {c.TEXT};
        font-size: 12px;
    }}

    /* ---------- Status bar ---------- */
    QStatusBar {{
        background: {c.SURFACE};
        border-top: 1px solid {c.BORDER};
        color: {c.TEXT_DIM};
    }}
    QStatusBar::item {{ border: none; }}

    /* ---------- Scrollbars ---------- */
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {c.SURFACE_3}; border-radius: 5px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {c.TEXT_FAINT}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {c.SURFACE_3}; border-radius: 5px; min-width: 30px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    QToolTip {{
        background: {c.SURFACE_3};
        color: {c.TEXT};
        border: 1px solid {c.BORDER};
        border-radius: 6px;
        padding: 5px 8px;
    }}

    /* ---------- Bridge: splitter ---------- */
    QSplitter#mainSplit::handle {{ background: {c.BORDER}; }}

    /* ---------- Bridge: folder tree (kiri) ---------- */
    QTreeView#folderTree {{
        background: {c.SURFACE};
        border: none;
        border-right: 1px solid {c.BORDER};
        padding: 6px 4px;
        show-decoration-selected: 1;
    }}
    QTreeView#folderTree::item {{
        padding: 4px 2px;
        border-radius: 6px;
        color: {c.TEXT_DIM};
    }}
    QTreeView#folderTree::item:hover {{ background: {c.SURFACE_2}; color: {c.TEXT}; }}
    QTreeView#folderTree::item:selected {{ background: {c.ACCENT_SOFT}; color: {c.TEXT}; }}

    /* ---------- Bridge: content grid (tengah) ---------- */
    QListWidget#contentGrid {{
        background: {c.BG};
        border: none;
        padding: 12px;
    }}
    QListWidget#contentGrid::item {{
        color: {c.TEXT_DIM};
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 6px 4px;
    }}
    QListWidget#contentGrid::item:hover {{ background: {c.SURFACE}; }}
    QListWidget#contentGrid::item:selected {{
        background: {c.ACCENT_SOFT};
        border: 1px solid {c.ACCENT};
        color: {c.TEXT};
    }}

    /* ---------- Bridge: inspector (kanan) ---------- */
    QTabWidget#inspector {{ background: {c.SURFACE}; }}
    QTabWidget#inspector::pane {{
        background: {c.SURFACE};
        border: none;
        border-left: 1px solid {c.BORDER};
    }}
    QTabWidget#inspector QTabBar::tab {{
        background: {c.SURFACE};
        color: {c.TEXT_FAINT};
        padding: 8px 16px;
        border: none;
        border-bottom: 2px solid transparent;
        font-size: 12px;
        font-weight: 600;
    }}
    QTabWidget#inspector QTabBar::tab:selected {{
        color: {c.TEXT};
        border-bottom: 2px solid {c.ACCENT};
    }}
    QTabWidget#inspector QTabBar::tab:hover {{ color: {c.TEXT_DIM}; }}
    QFrame#propsBox {{
        background: {c.SURFACE_2};
        border: 1px solid {c.BORDER_SOFT};
        border-radius: 10px;
    }}

    /* ---------- Export target rows ---------- */
    QFrame#targetRow {{
        background: {c.SURFACE_2};
        border: 1px solid {c.BORDER_SOFT};
        border-radius: 10px;
    }}
    QFrame#targetRow QLineEdit {{
        background: {c.SURFACE};
        font-weight: 600;
    }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {c.BORDER}; border-radius: 5px; background: {c.SURFACE};
    }}
    QCheckBox::indicator:checked {{
        background: {c.SUCCESS}; border-color: {c.SUCCESS};
    }}

    /* ---------- Slider ---------- */
    QSlider::groove:horizontal {{ height: 4px; background: {c.SURFACE_3}; border-radius: 2px; }}
    QSlider::handle:horizontal {{
        background: {c.ACCENT}; width: 14px; height: 14px;
        margin: -6px 0; border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{ background: {c.ACCENT_HOVER}; }}
    """
