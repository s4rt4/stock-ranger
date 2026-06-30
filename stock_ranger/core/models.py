"""Data model bersama untuk pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class JpgMode(str, Enum):
    AUTO = "auto"       # rasterize dari SVG via Inkscape
    MANUAL = "manual"   # pakai JPG existing yang di-pair


class ColorMode(str, Enum):
    """Colorspace output EPS.

    RGB = default microstock (Shutterstock approve & konversi semua ke sRGB).
    CMYK = untuk klien cetak (gs black-generate netral/gelap; ICC opsional).
    """

    RGB = "rgb"
    CMYK = "cmyk"


class OutputMode(str, Enum):
    """Mode paket output sesuai kebijakan microstock."""

    EPS_ONLY = "eps_only"      # Kel.1: cuma EPS + metadata
    PAIR_LOOSE = "pair_loose"  # Kel.2: EPS + JPG (nama+metadata sama), tanpa zip
    PAIR_ZIP = "pair_zip"      # Kel.3: EPS + JPG di-zip per pasangan


class JpgSizeRule(str, Enum):
    """Aturan ukuran JPG — selalu JAGA aspect ratio (tidak distorsi)."""

    LONGEST_SIDE = "longest_side"      # value = px sisi terpanjang
    MAX_MEGAPIXELS = "max_megapixels"  # value = batas megapixel


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
    output_mode: OutputMode = OutputMode.PAIR_ZIP
    jpg_rule: JpgSizeRule = JpgSizeRule.LONGEST_SIDE
    jpg_value: int = 4000           # px (LONGEST_SIDE) atau MP (MAX_MEGAPIXELS)
    dpi: int = 300
    jpg_quality: int = 92
    jpg_mode: JpgMode = JpgMode.AUTO
    color_mode: ColorMode = ColorMode.RGB  # default microstock (sRGB)
    icc_profile: Path | None = None  # None → resolusi otomatis (SWOP / gs default); hanya CMYK

    @property
    def needs_jpg(self) -> bool:
        return self.output_mode != OutputMode.EPS_ONLY


@dataclass
class ExportTarget:
    """Preset satu microstock — mode paket + aturan ukuran JPG."""

    name: str
    output_mode: OutputMode = OutputMode.PAIR_ZIP
    jpg_rule: JpgSizeRule = JpgSizeRule.LONGEST_SIDE
    jpg_value: int = 4000
    jpg_quality: int = 92
    enabled: bool = True

    @property
    def needs_jpg(self) -> bool:
        return self.output_mode != OutputMode.EPS_ONLY

    def summary(self) -> str:
        mode = {
            OutputMode.EPS_ONLY: "EPS",
            OutputMode.PAIR_LOOSE: "EPS+JPG",
            OutputMode.PAIR_ZIP: "ZIP(EPS+JPG)",
        }[self.output_mode]
        if self.output_mode == OutputMode.EPS_ONLY:
            return mode
        unit = "px" if self.jpg_rule == JpgSizeRule.LONGEST_SIDE else "MP"
        return f"{mode} · {self.jpg_value}{unit}"


@dataclass
class JobResult:
    source: Path
    eps_path: Path | None = None
    jpg_path: Path | None = None
    zip_path: Path | None = None
    outputs: dict[str, list[Path]] = field(default_factory=dict)  # target → files
    ok: bool = False
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
