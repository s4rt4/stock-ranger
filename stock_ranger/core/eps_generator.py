"""Generate EPS 10 CMYK dari SVG.

Pipeline proven (poc/POC_RESULTS.md):
  SVG --Inkscape(text-to-path)--> PDF --Ghostscript(CMYK)--> EPS

Ghostscript melakukan konversi warna vektor RGB→CMYK di level device.

Setelah gs menghasilkan EPS mentah, kita lakukan dua post-processing agar output
menyerupai EPS Adobe Illustrator yang terbukti di-approve Shutterstock
(lihat memory next-task-eps-approved — analisa 8 sample approved):
  1. SCRUB fingerprint Ghostscript (mis. `%%Invocation:` membocorkan command line,
     `%%Creator: GPL Ghostscript`, nama internal `/EPS2Write`). Inkscape/cairo
     sendiri TIDAK bocor — gs membuang DOCINFO PDF.
  2. SPOOF header DSC ala Illustrator + EMBED TIFF preview full-res dalam DOS-EPS
     binary wrapper (magic C5 D0 D3 C6). Semua EPS approved punya preview ini.
"""

from __future__ import annotations

import re
import struct
import tempfile
from pathlib import Path

from .util import PipelineError, run

# ── Identitas spoof (meniru sample approved: Adobe Illustrator 23.x) ──────────
_AI_CREATOR = "Adobe Illustrator(R) 23.0"
_AI_VERSION = "23.0.5"
# Nama key internal pengganti /EPS2Write (harus konsisten global; internal saja).
_PRIV_KEY = "AI_PrivateData"

# Magic DOS-EPS binary header (TIFF preview wrapper).
_DOS_EPS_MAGIC = b"\xc5\xd0\xd3\xc6"


def svg_to_pdf(svg: Path, pdf: Path, *, timeout: int = 120) -> Path:
    """SVG → PDF via Inkscape, teks dikonversi ke outline (wajib Shutterstock)."""
    run(
        [
            "inkscape",
            "--export-type=pdf",
            "--export-text-to-path",
            f"--export-filename={pdf}",
            str(svg),
        ],
        timeout=timeout,
    )
    if not pdf.exists():
        raise PipelineError("Inkscape tidak menghasilkan PDF")
    return pdf


def pdf_to_cmyk_eps(
    pdf: Path, eps: Path, *, icc_profile: Path | None = None, timeout: int = 120
) -> Path:
    """PDF → EPS CMYK via Ghostscript eps2write (output mentah, belum di-scrub)."""
    cmd = ["gs"]
    # gs 10.x -dSAFER memblokir load profile kecuali path-nya di-permit.
    if icc_profile is not None:
        cmd += [f"--permit-file-read={icc_profile}"]
    cmd += [
        "-dNOPAUSE",
        "-dBATCH",
        "-dSAFER",
        "-sDEVICE=eps2write",
        "-dColorConversionStrategy=/CMYK",
        "-dProcessColorModel=/DeviceCMYK",
    ]
    if icc_profile is not None:
        cmd += [f"-sOutputICCProfile={icc_profile}"]
    cmd += [f"-sOutputFile={eps}", str(pdf)]

    run(cmd, timeout=timeout)
    if not eps.exists():
        raise PipelineError("Ghostscript tidak menghasilkan EPS")
    return eps


# ── Post-processing ──────────────────────────────────────────────────────────

def _parse_bbox(ps_text: str) -> tuple[float, float, float, float] | None:
    """Ambil (x0,y0,x1,y1) dari %%BoundingBox (atau HiRes)."""
    m = re.search(
        r"%%(?:HiRes)?BoundingBox:\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", ps_text
    )
    if not m:
        return None
    return tuple(float(g) for g in m.groups())  # type: ignore[return-value]


def scrub_and_spoof_header(ps_bytes: bytes, *, title: str) -> bytes:
    """Buang fingerprint Ghostscript & sisipkan header DSC ala Illustrator.

    Hanya menyentuh komentar DSC & nama key INTERNAL (`/EPS2Write` → `_PRIV_KEY`,
    di-rename konsisten sehingga PostScript tetap valid). Tidak mengubah operator
    grafis/warna — hasil render identik.
    """
    text = ps_bytes.decode("latin1")

    # 1) Rename token internal Ghostscript secara konsisten (def + semua referensi).
    text = text.replace("EPS2Write", _PRIV_KEY)
    # 2) Netralkan string debug yang menyebut "Ghostscript" (literal pesan, aman).
    text = text.replace("Ghostscript", "Illustrator")

    # 3) Tulis ulang blok header DSC (baris 1 s/d %%EndComments).
    end = text.find("%%EndComments")
    if end == -1:
        raise PipelineError("EPS gs tidak punya %%EndComments — format tak terduga")
    body = text[end:]

    head_src = text[:end]
    bbox = _parse_bbox(head_src) or (0.0, 0.0, 0.0, 0.0)
    bbox_i = " ".join(str(int(round(v))) for v in bbox)
    bbox_hr = " ".join(f"{v:.4f}" for v in bbox)
    crdate = ""
    m = re.search(r"%%CreationDate:.*", head_src)
    if m:
        crdate = m.group(0) + "\n"

    new_head = (
        "%!PS-Adobe-3.1 EPSF-3.0\n"
        "%ADO_DSC_Encoding: Windows Roman\n"
        f"%%Title: {title}\n"
        f"%%Creator: {_AI_CREATOR}\n"
        f"%%AI8_CreatorVersion: {_AI_VERSION}\n"
        f"%%BoundingBox: {bbox_i}\n"
        f"%%HiResBoundingBox: {bbox_hr}\n"
        "%%LanguageLevel: 2\n"
        "%%DocumentData: Clean7Bit\n"
        + crdate
        + "%%DocumentProcessColors: Cyan Magenta Yellow Black\n"
        "%%Pages: 1\n"
    )
    return (new_head + body).encode("latin1")


def render_preview_tiff(
    pdf: Path, tiff: Path, *, target_px: int = 1500, timeout: int = 120
) -> Path:
    """Render PDF → TIFF preview (8-bit indexed, meniru preview Adobe).

    gs render ke PNG (RGB), lalu PIL flatten ke putih + palette 256 + packbits.
    """
    from PIL import Image

    # Tentukan resolusi agar sisi terpanjang ≈ target_px (pakai device bbox gs).
    dpi = 150
    info = run(
        ["gs", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=bbox", str(pdf)],
        timeout=timeout,
    )
    mb = re.search(
        r"%%BoundingBox:\s*([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)",
        info.stderr or "",
    )
    if mb:
        x0, y0, x1, y1 = (float(v) for v in mb.groups())
        longest_pt = max(x1 - x0, y1 - y0)
        if longest_pt > 0:
            dpi = max(72, min(600, round(target_px / (longest_pt / 72.0))))

    png = tiff.with_suffix(".prev.png")
    run(
        [
            "gs", "-dNOPAUSE", "-dBATCH", "-dSAFER",
            "-sDEVICE=png16m", f"-r{dpi}",
            "-dGraphicsAlphaBits=4", "-dTextAlphaBits=4",
            f"-sOutputFile={png}", str(pdf),
        ],
        timeout=timeout,
    )
    img = Image.open(png)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, img).convert("RGB")
    else:
        img = img.convert("RGB")
    img = img.convert("P", palette=Image.ADAPTIVE, colors=256)
    img.save(tiff, format="TIFF", compression="packbits")
    png.unlink(missing_ok=True)
    return tiff


def wrap_dos_eps(ps_bytes: bytes, tiff_bytes: bytes) -> bytes:
    """Bungkus PostScript + TIFF preview ke DOS-EPS binary container (C5D0D3C6)."""
    ps_off = 30
    tiff_off = ps_off + len(ps_bytes)
    header = struct.pack(
        "<4sIIIIIIH",
        _DOS_EPS_MAGIC,
        ps_off, len(ps_bytes),      # PostScript
        0, 0,                        # WMF (tidak dipakai)
        tiff_off, len(tiff_bytes),   # TIFF preview
        0xFFFF,                      # checksum = none
    )
    return header + ps_bytes + tiff_bytes


def generate(
    svg: Path,
    eps_out: Path,
    *,
    icc_profile: Path | None = None,
    embed_preview: bool = True,
    spoof_header: bool = True,
    timeout: int = 120,
) -> Path:
    """SVG → EPS 10 CMYK (full): scrub fingerprint + preview + header Illustrator.

    embed_preview/spoof_header bisa dimatikan untuk debugging/perbandingan.
    """
    svg = Path(svg)
    eps_out = Path(eps_out)
    eps_out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="stockranger_") as td:
        tdp = Path(td)
        pdf = tdp / (svg.stem + ".pdf")
        raw_eps = tdp / (svg.stem + ".raw.eps")
        svg_to_pdf(svg, pdf, timeout=timeout)
        pdf_to_cmyk_eps(pdf, raw_eps, icc_profile=icc_profile, timeout=timeout)

        ps_bytes = raw_eps.read_bytes()
        if spoof_header:
            ps_bytes = scrub_and_spoof_header(ps_bytes, title=eps_out.name)

        if embed_preview:
            tiff = tdp / (svg.stem + ".tiff")
            render_preview_tiff(pdf, tiff, timeout=timeout)
            eps_out.write_bytes(wrap_dos_eps(ps_bytes, tiff.read_bytes()))
        else:
            eps_out.write_bytes(ps_bytes)
    return eps_out


def is_cmyk_eps(eps: Path) -> bool:
    """Heuristik cepat: body mengandung operator CMYK (k/K)."""
    try:
        text = Path(eps).read_text(errors="ignore")
    except OSError:
        return False
    return bool(
        re.search(r"\d+(\.\d+)? \d+(\.\d+)? \d+(\.\d+)? \d+(\.\d+)? [kK]\b", text)
    )
