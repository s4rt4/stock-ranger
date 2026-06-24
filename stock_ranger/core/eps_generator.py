"""Generate EPS 10 CMYK dari SVG.

Pipeline proven (poc/POC_RESULTS.md):
  SVG --Inkscape(text-to-path)--> PDF --Ghostscript(CMYK)--> EPS

Ghostscript melakukan konversi warna vektor RGB→CMYK di level device.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from .util import PipelineError, run


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
    """PDF → EPS CMYK via Ghostscript eps2write."""
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


def generate(
    svg: Path,
    eps_out: Path,
    *,
    icc_profile: Path | None = None,
    timeout: int = 120,
) -> Path:
    """SVG → EPS 10 CMYK (full). PDF antara dibuat di tempdir."""
    svg = Path(svg)
    eps_out = Path(eps_out)
    eps_out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="stockranger_") as td:
        pdf = Path(td) / (svg.stem + ".pdf")
        svg_to_pdf(svg, pdf, timeout=timeout)
        pdf_to_cmyk_eps(pdf, eps_out, icc_profile=icc_profile, timeout=timeout)
    return eps_out


def is_cmyk_eps(eps: Path) -> bool:
    """Heuristik cepat: body mengandung operator CMYK (k/K)."""
    try:
        text = Path(eps).read_text(errors="ignore")
    except OSError:
        return False
    import re

    return bool(re.search(r"\d+(\.\d+)? \d+(\.\d+)? \d+(\.\d+)? \d+(\.\d+)? [kK]\b", text))
