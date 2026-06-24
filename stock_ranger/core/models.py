"""Data model bersama untuk pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class JpgMode(str, Enum):
    AUTO = "auto"       # rasterize dari SVG via Inkscape
    MANUAL = "manual"   # pakai JPG existing yang di-pair


@dataclass
class Metadata:
    """Metadata Shutterstock — di-embed ke EPS & JPG."""

    title: str = ""
    description: str = ""
    keywords: list[str] = field(default_factory=list)

    def cleaned_keywords(self) -> list[str]:
        """Keyword unik (case-insensitive), urutan dipertahankan."""
        out: list[str] = []
        lowered: set[str] = set()
        for k in self.keywords:
            k = k.strip()
            if k and k.lower() not in lowered:
                lowered.add(k.lower())
                out.append(k)
        return out


@dataclass
class OutputSettings:
    out_dir: Path = Path.home() / "StockRanger" / "output"
    jpg_width: int = 4000
    jpg_height: int = 4000
    dpi: int = 300
    jpg_quality: int = 92
    jpg_mode: JpgMode = JpgMode.AUTO
    zip_per_pair: bool = True       # satu ZIP per pasangan
    icc_profile: Path | None = None  # None → resolusi otomatis (SWOP / gs default)


@dataclass
class JobResult:
    source: Path
    eps_path: Path | None = None
    jpg_path: Path | None = None
    zip_path: Path | None = None
    ok: bool = False
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
