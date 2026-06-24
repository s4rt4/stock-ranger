"""Live preview + analisis gamut via LittleCMS (PIL.ImageCms).

- render_rgb: rasterize SVG kecil (Inkscape) untuk preview RGB.
- soft_proof: simulasi tampilan CMYK (roundtrip RGB→CMYK→RGB lewat ICC).
- gamut_count: jumlah warna yang bergeser signifikan saat dikonversi ke CMYK.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageCms

from .util import PipelineError, run

_SRGB = ImageCms.createProfile("sRGB")


@dataclass
class PreviewResult:
    rgb: Image.Image
    cmyk_sim: Image.Image
    gamut_out: int


def render_rgb(svg: Path, *, max_px: int = 480, timeout: int = 60) -> Image.Image:
    """Rasterize SVG ke PIL RGB image kecil untuk preview."""
    svg = Path(svg)
    with tempfile.TemporaryDirectory(prefix="sr_prev_") as td:
        png = Path(td) / "p.png"
        run(
            [
                "inkscape",
                "--export-type=png",
                f"--export-width={max_px}",
                f"--export-filename={png}",
                str(svg),
            ],
            timeout=timeout,
        )
        if not png.exists():
            raise PipelineError("Inkscape gagal render preview")
        with Image.open(png) as im:
            im.load()
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, (255, 255, 255))
                bg.paste(im, mask=im.split()[-1])
                return bg
            return im.convert("RGB")


def _transforms(icc_path: Path):
    cmyk_prof = ImageCms.getOpenProfile(str(icc_path))
    to_cmyk = ImageCms.buildTransform(
        _SRGB, cmyk_prof, "RGB", "CMYK",
        renderingIntent=ImageCms.Intent.PERCEPTUAL,
    )
    to_rgb = ImageCms.buildTransform(
        cmyk_prof, _SRGB, "CMYK", "RGB",
        renderingIntent=ImageCms.Intent.PERCEPTUAL,
    )
    return to_cmyk, to_rgb


def soft_proof(img_rgb: Image.Image, icc_path: Path) -> Image.Image:
    """Simulasi tampilan CMYK: RGB → CMYK → RGB."""
    to_cmyk, to_rgb = _transforms(icc_path)
    cmyk = ImageCms.applyTransform(img_rgb, to_cmyk)
    return ImageCms.applyTransform(cmyk, to_rgb)


def gamut_count(img_rgb: Image.Image, icc_path: Path, *, threshold: int = 16) -> int:
    """Jumlah warna dominan yang out-of-gamut (bergeser > threshold saat CMYK)."""
    # Kuantisasi ke palet warna dominan supaya cepat & relevan secara visual.
    q = img_rgb.quantize(colors=64).convert("RGB")
    colors = q.getcolors(maxcolors=4096) or []
    if not colors:
        return 0

    to_cmyk, to_rgb = _transforms(icc_path)
    # Bangun gambar 1-baris berisi warna unik, roundtrip sekali (efisien).
    uniq = [rgb for _count, rgb in colors]
    strip = Image.new("RGB", (len(uniq), 1))
    strip.putdata(uniq)
    back = ImageCms.applyTransform(ImageCms.applyTransform(strip, to_cmyk), to_rgb)
    back_px = list(back.getdata())

    out = 0
    for orig, got in zip(uniq, back_px):
        if max(abs(a - b) for a, b in zip(orig, got)) > threshold:
            out += 1
    return out


def analyze(svg: Path, icc_path: Path | None, *, max_px: int = 480) -> PreviewResult:
    """Render RGB + CMYK-sim + hitung gamut dalam satu panggilan."""
    rgb = render_rgb(svg, max_px=max_px)
    if icc_path is None:
        return PreviewResult(rgb=rgb, cmyk_sim=rgb.copy(), gamut_out=0)
    cmyk_sim = soft_proof(rgb, icc_path)
    gout = gamut_count(rgb, icc_path)
    return PreviewResult(rgb=rgb, cmyk_sim=cmyk_sim, gamut_out=gout)
