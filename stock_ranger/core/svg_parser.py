"""Validasi & inspeksi SVG input."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

_SVG_NS = "http://www.w3.org/2000/svg"
_XLINK = "http://www.w3.org/1999/xlink"


@dataclass
class SvgInfo:
    path: Path
    valid: bool
    width: str | None = None
    height: str | None = None
    has_raster: bool = False       # ada <image> embedded (bukan pure vector)
    has_text: bool = False         # ada <text> (perlu text-to-path)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def parse(path: Path | str) -> SvgInfo:
    path = Path(path)
    if not path.exists():
        return SvgInfo(path, valid=False, error="File tidak ada")
    if path.suffix.lower() != ".svg":
        return SvgInfo(path, valid=False, error="Bukan file .svg")

    try:
        tree = etree.parse(str(path))
    except etree.XMLSyntaxError as e:
        return SvgInfo(path, valid=False, error=f"SVG tidak valid: {e}")

    root = tree.getroot()
    if not root.tag.endswith("svg"):
        return SvgInfo(path, valid=False, error="Root bukan elemen <svg>")

    info = SvgInfo(
        path=path,
        valid=True,
        width=root.get("width"),
        height=root.get("height"),
    )

    images = root.findall(f".//{{{_SVG_NS}}}image")
    info.has_raster = len(images) > 0
    if info.has_raster:
        info.warnings.append(
            f"{len(images)} embedded raster image — hasil EPS tidak akan pure vector"
        )

    texts = root.findall(f".//{{{_SVG_NS}}}text")
    info.has_text = len(texts) > 0
    if info.has_text:
        info.warnings.append("Mengandung <text> — akan dikonversi ke path otomatis")

    return info
