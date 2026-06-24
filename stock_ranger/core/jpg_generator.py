"""Generate JPG preview dari SVG (mode auto) atau import (mode manual).

Auto: Inkscape rasterize SVG → PNG, lalu Pillow resize + simpan JPG.
Manual: pakai JPG existing (di-pair berdasar nama file).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image

from .util import PipelineError, run


def rasterize(
    svg: Path,
    jpg_out: Path,
    *,
    width: int = 4000,
    height: int = 4000,
    dpi: int = 300,
    quality: int = 92,
    timeout: int = 180,
) -> Path:
    """SVG → JPG. Inkscape export PNG (lossless), lalu Pillow → JPG."""
    svg = Path(svg)
    jpg_out = Path(jpg_out)
    jpg_out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="stockranger_jpg_") as td:
        png = Path(td) / (svg.stem + ".png")
        run(
            [
                "inkscape",
                "--export-type=png",
                f"--export-width={width}",
                f"--export-height={height}",
                f"--export-dpi={dpi}",
                f"--export-filename={png}",
                str(svg),
            ],
            timeout=timeout,
        )
        if not png.exists():
            raise PipelineError("Inkscape tidak menghasilkan PNG")

        with Image.open(png) as im:
            # Flatten alpha ke putih (JPG tidak punya alpha)
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, (255, 255, 255))
                bg.paste(im, mask=im.split()[-1])
                im = bg
            else:
                im = im.convert("RGB")
            im.save(jpg_out, "JPEG", quality=quality, dpi=(dpi, dpi))
    return jpg_out


def import_existing(jpg_src: Path, jpg_out: Path, *, quality: int = 92) -> Path:
    """Mode manual: normalisasi JPG existing (re-encode RGB)."""
    jpg_out = Path(jpg_out)
    jpg_out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(jpg_src) as im:
        im.convert("RGB").save(jpg_out, "JPEG", quality=quality)
    return jpg_out
