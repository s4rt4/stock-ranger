"""Generate JPG preview dari SVG (mode auto) atau import (mode manual).

Auto: Inkscape rasterize SVG → PNG, lalu Pillow resize + simpan JPG.
Manual: pakai JPG existing (di-pair berdasar nama file).
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

from PIL import Image

from .models import JpgSizeRule
from .util import PipelineError, run


def target_dimensions(
    w: int, h: int, rule: JpgSizeRule, value: float
) -> tuple[int, int]:
    """Hitung (w,h) hasil DENGAN JAGA aspect ratio sesuai aturan microstock."""
    if w <= 0 or h <= 0:
        return max(1, int(value)), max(1, int(value))
    if rule == JpgSizeRule.MAX_MEGAPIXELS:
        cur_mp = (w * h) / 1_000_000
        scale = math.sqrt(value / cur_mp) if cur_mp > 0 else 1.0
    else:  # LONGEST_SIDE
        scale = value / max(w, h)
    return max(1, round(w * scale)), max(1, round(h * scale))


def _flatten(im: Image.Image) -> Image.Image:
    """Buang alpha ke putih (JPG tak punya alpha)."""
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        return bg
    return im.convert("RGB")


def rasterize(
    svg: Path,
    jpg_out: Path,
    *,
    rule: JpgSizeRule = JpgSizeRule.LONGEST_SIDE,
    value: float = 4000,
    dpi: int = 300,
    quality: int = 92,
    timeout: int = 180,
) -> Path:
    """SVG → JPG (aspect ratio terjaga). Inkscape render natural, Pillow resize+encode."""
    svg = Path(svg)
    jpg_out = Path(jpg_out)
    jpg_out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="stockranger_jpg_") as td:
        png = Path(td) / (svg.stem + ".png")
        # Render natural (HANYA dpi, biarkan Inkscape jaga aspect SVG asli).
        run(
            [
                "inkscape",
                "--export-type=png",
                f"--export-dpi={max(dpi, 96)}",
                f"--export-filename={png}",
                str(svg),
            ],
            timeout=timeout,
        )
        if not png.exists():
            raise PipelineError("Inkscape tidak menghasilkan PNG")

        with Image.open(png) as im:
            im = _flatten(im)
            tw, th = target_dimensions(im.width, im.height, rule, value)
            if (tw, th) != (im.width, im.height):
                im = im.resize((tw, th), Image.LANCZOS)
            im.save(jpg_out, "JPEG", quality=quality, dpi=(dpi, dpi))
    return jpg_out


def import_existing(
    jpg_src: Path,
    jpg_out: Path,
    *,
    rule: JpgSizeRule | None = None,
    value: float = 0,
    quality: int = 92,
) -> Path:
    """Mode manual: normalisasi JPG existing (re-encode RGB), opsional resize."""
    jpg_out = Path(jpg_out)
    jpg_out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(jpg_src) as im:
        im = im.convert("RGB")
        if rule is not None and value:
            tw, th = target_dimensions(im.width, im.height, rule, value)
            if (tw, th) != (im.width, im.height):
                im = im.resize((tw, th), Image.LANCZOS)
        im.save(jpg_out, "JPEG", quality=quality)
    return jpg_out
