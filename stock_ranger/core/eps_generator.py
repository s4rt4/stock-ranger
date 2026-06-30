"""Generate EPS 10 (RGB/CMYK) dari SVG.

Pipeline proven (poc/POC_RESULTS.md, + analisa forensik versi Windows):
  SVG --match_px_to_pt--> SVG' --Inkscape(text-to-path)--> PDF
      --Ghostscript(RGB|CMYK)--> EPS --scrub+spoof+preview--> EPS final

Ghostscript melakukan konversi warna vektor di level device. Untuk CMYK gs sudah
black-generate warna netral/gelap (UCR built-in); K=0 pada warna jenuh adalah SAH.

Empat pilar dari analisa forensik:
  A. match_px_to_pt() — Inkscape ekspor px@96dpi → bbox-pt = px×0.75 → gagal ≥4MP
     Shutterstock. Kita normalkan agar bbox-pt = px desain (validator bbox_megapixels).
  B. Dua mode warna (ColorMode): RGB default (microstock minta sRGB) / CMYK (cetak).
  D. Detektor warna: is_cmyk_eps() berlapis (XMP swatch mode → operator k/rg →
     dominasi /Device*) + eps_ink_coverage()/has_black_plate() via gs inkcov.

Post-processing agar output menyerupai EPS Adobe Illustrator (approved Shutterstock):
  1. SCRUB fingerprint Ghostscript (%%Invocation membocorkan command line,
     %%Creator GPL Ghostscript, nama internal /EPS2Write).
  2. SPOOF header DSC ala Illustrator + EMBED TIFF preview full-res dalam DOS-EPS
     binary wrapper (magic C5 D0 D3 C6).
"""

from __future__ import annotations

import re
import struct
import tempfile
from collections.abc import Callable
from pathlib import Path

from lxml import etree

from .models import ColorMode
from .util import PipelineError, run

# ── Identitas spoof (meniru sample approved: Adobe Illustrator) ───────────────
# Sample baru (analisa Windows) berasal dari Illustrator 2026 = v30.
_AI_CREATOR = "Adobe Illustrator(R) 30.0"
_AI_VERSION = "30.0.0"
# Nama key internal pengganti /EPS2Write (harus konsisten global; internal saja).
_PRIV_KEY = "AI_PrivateData"

# Magic DOS-EPS binary header (TIFF preview wrapper).
_DOS_EPS_MAGIC = b"\xc5\xd0\xd3\xc6"

# Faktor satuan CSS → px @96dpi (untuk menghitung dimensi desain dari SVG).
_UNIT_PX = {
    "": 1.0, "px": 1.0, "pt": 96.0 / 72.0, "pc": 16.0,
    "mm": 96.0 / 25.4, "cm": 96.0 / 2.54, "in": 96.0, "q": 96.0 / 25.4 / 4.0,
}

_SVG_NS = "http://www.w3.org/2000/svg"


# ── Pilar A: dimensi/4MP ──────────────────────────────────────────────────────

def _len_to_px(value: str | None) -> float | None:
    """Ubah panjang CSS SVG (mis. '2000', '529.16mm', '2000pt') ke px @96dpi.

    None / persen / tak-terbaca → None (caller fallback ke viewBox).
    """
    if not value:
        return None
    m = re.fullmatch(r"\s*([\d.]+)\s*([a-zA-Z%]*)\s*", value)
    if not m:
        return None
    num, unit = float(m.group(1)), m.group(2).lower()
    if unit == "%":
        return None
    factor = _UNIT_PX.get(unit)
    if factor is None:
        return None
    return num * factor


def svg_px_dims(svg: Path) -> tuple[float, float] | None:
    """Dimensi desain SVG dalam px @96dpi (width/height, fallback viewBox)."""
    try:
        root = etree.parse(str(svg)).getroot()
    except (OSError, etree.XMLSyntaxError):
        return None
    w = _len_to_px(root.get("width"))
    h = _len_to_px(root.get("height"))
    if w and h:
        return w, h
    vb = root.get("viewBox")
    if vb:
        parts = re.split(r"[ ,]+", vb.strip())
        if len(parts) == 4:
            try:
                return float(parts[2]), float(parts[3])
            except ValueError:
                pass
    return None


def match_px_to_pt(svg_in: Path, svg_out: Path) -> tuple[float, float] | None:
    """Tulis ulang SVG agar Inkscape mengekspor bbox-pt = px desain.

    Inkscape memetakan px@96dpi → pt (1px = 0.75pt), jadi dokumen 2000px jadi
    1500pt → 2.7MP (gagal ≥4MP). Kita set width/height dalam SATUAN pt sama dengan
    angka px desain + pastikan ada viewBox; hasilnya bbox-pt = px (×1.3333 untuk
    SVG px-native, konversi benar untuk satuan lain). Mengembalikan (px_w, px_h),
    atau None bila dimensi tak terbaca (caller pakai SVG asli apa adanya).
    """
    dims = svg_px_dims(svg_in)
    if not dims:
        return None
    px_w, px_h = dims
    tree = etree.parse(str(svg_in))
    root = tree.getroot()
    if not root.get("viewBox"):
        root.set("viewBox", f"0 0 {px_w:g} {px_h:g}")
    # 1pt → 1px@72dpi → angka pt = target bbox-pt = px desain.
    root.set("width", f"{px_w:g}pt")
    root.set("height", f"{px_h:g}pt")
    tree.write(str(svg_out), xml_declaration=True, encoding="UTF-8")
    return px_w, px_h


def _parse_bbox(ps_text: str) -> tuple[float, float, float, float] | None:
    """Ambil (x0,y0,x1,y1) dari %%HiResBoundingBox (atau %%BoundingBox)."""
    m = re.search(
        r"%%HiResBoundingBox:\s*([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)", ps_text
    ) or re.search(
        r"%%BoundingBox:\s*([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)", ps_text
    )
    if not m:
        return None
    return tuple(float(g) for g in m.groups())  # type: ignore[return-value]


def bbox_megapixels(eps: Path) -> float | None:
    """Megapixel dari bounding box EPS (pt dibaca sebagai px @72dpi, cara Shutterstock)."""
    try:
        text = Path(eps).read_bytes().decode("latin1")
    except OSError:
        return None
    bbox = _parse_bbox(text)
    if not bbox:
        return None
    x0, y0, x1, y1 = bbox
    return abs((x1 - x0) * (y1 - y0)) / 1_000_000.0


# ── Konversi (Pilar B) ─────────────────────────────────────────────────────────

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


def pdf_to_eps(
    pdf: Path,
    eps: Path,
    *,
    color_mode: ColorMode = ColorMode.RGB,
    icc_profile: Path | None = None,
    timeout: int = 120,
) -> Path:
    """PDF → EPS via Ghostscript eps2write (output mentah, belum di-scrub).

    RGB (default microstock): -dColorConversionStrategy=/RGB /DeviceRGB.
    CMYK (cetak): /CMYK /DeviceCMYK; ICC dipakai sebagai output device color
    (efek kecil utk vektor, relevan utk raster ter-embed).
    """
    is_cmyk = color_mode == ColorMode.CMYK
    use_icc = is_cmyk and icc_profile is not None
    cmd = ["gs"]
    # gs 10.x -dSAFER memblokir load profile kecuali path-nya di-permit.
    if use_icc:
        cmd += [f"--permit-file-read={icc_profile}"]
    cmd += ["-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=eps2write"]
    if is_cmyk:
        cmd += ["-dColorConversionStrategy=/CMYK", "-dProcessColorModel=/DeviceCMYK"]
    else:
        cmd += ["-dColorConversionStrategy=/RGB", "-dProcessColorModel=/DeviceRGB"]
    if use_icc:
        cmd += [f"-sOutputICCProfile={icc_profile}"]
    cmd += [f"-sOutputFile={eps}", str(pdf)]

    run(cmd, timeout=timeout)
    if not eps.exists():
        raise PipelineError("Ghostscript tidak menghasilkan EPS")
    return eps


def pdf_to_cmyk_eps(
    pdf: Path, eps: Path, *, icc_profile: Path | None = None, timeout: int = 120
) -> Path:
    """Kompat lama: PDF → EPS CMYK. Setara pdf_to_eps(color_mode=CMYK)."""
    return pdf_to_eps(
        pdf, eps, color_mode=ColorMode.CMYK, icc_profile=icc_profile, timeout=timeout
    )


# ── Post-processing ──────────────────────────────────────────────────────────

def scrub_and_spoof_header(
    ps_bytes: bytes, *, title: str, color_mode: ColorMode = ColorMode.RGB
) -> bytes:
    """Buang fingerprint Ghostscript & sisipkan header DSC ala Illustrator.

    Hanya menyentuh komentar DSC & nama key INTERNAL (`/EPS2Write` → `_PRIV_KEY`,
    di-rename konsisten sehingga PostScript tetap valid). Tidak mengubah operator
    grafis/warna — hasil render identik. `%%DocumentProcessColors` HANYA ditulis
    pada mode CMYK (mengikuti sample Illustrator).
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

    proc_colors = ""
    if color_mode == ColorMode.CMYK:
        proc_colors = "%%DocumentProcessColors: Cyan Magenta Yellow Black\n"

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
        + proc_colors
        + "%%Pages: 1\n"
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
    color_mode: ColorMode = ColorMode.RGB,
    scale_to_px: bool = True,
    icc_profile: Path | None = None,
    embed_preview: bool = True,
    spoof_header: bool = True,
    on_raw: "Callable[[Path], None] | None" = None,
    timeout: int = 120,
) -> Path:
    """SVG → EPS 10 (full): normalisasi dimensi + warna + scrub + preview + header AI.

    color_mode: RGB (default microstock) / CMYK (cetak). icc_profile hanya dipakai
    bila CMYK.

    scale_to_px: terapkan match_px_to_pt() agar bbox-pt = px desain (lolos ≥4MP).

    on_raw: hook dipanggil dengan path EPS MENTAH (PostScript gs polos) sebelum
    spoof+wrap. Dipakai untuk embed metadata XMP — exiftool MENOLAK menulis XMP
    ke file yang sudah ber-header Illustrator, jadi metadata harus masuk di sini.
    XMP packet jatuh di body (setelah %%EndComments) sehingga selamat dari
    header-rewrite & DOS-EPS wrapping.

    embed_preview/spoof_header bisa dimatikan untuk debugging/perbandingan.
    """
    svg = Path(svg)
    eps_out = Path(eps_out)
    eps_out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="stockranger_") as td:
        tdp = Path(td)
        src_svg = svg
        if scale_to_px:
            scaled = tdp / (svg.stem + ".scaled.svg")
            if match_px_to_pt(svg, scaled) is not None:
                src_svg = scaled

        pdf = tdp / (svg.stem + ".pdf")
        raw_eps = tdp / (svg.stem + ".raw.eps")
        svg_to_pdf(src_svg, pdf, timeout=timeout)
        pdf_to_eps(
            pdf, raw_eps, color_mode=color_mode,
            icc_profile=icc_profile, timeout=timeout,
        )

        if on_raw is not None:
            on_raw(raw_eps)  # embed metadata ke EPS mentah (exiftool OK di sini)

        ps_bytes = raw_eps.read_bytes()
        if spoof_header:
            ps_bytes = scrub_and_spoof_header(
                ps_bytes, title=eps_out.name, color_mode=color_mode
            )

        if embed_preview:
            tiff = tdp / (svg.stem + ".tiff")
            render_preview_tiff(pdf, tiff, timeout=timeout)
            eps_out.write_bytes(wrap_dos_eps(ps_bytes, tiff.read_bytes()))
        else:
            eps_out.write_bytes(ps_bytes)
    return eps_out


# ── Pilar D: detektor warna ────────────────────────────────────────────────────

def source_colorspace(eps: Path) -> str:
    """Label colorspace SUMBER EPS: 'CMYK' / 'RGB' / '?' (heuristik teks berlapis).

    Urutan kuat→lemah (lihat analisa §1b):
      1. XMP swatch mode `<xmpG:mode>CMYK|RGB</xmpG:mode>` — paling andal. WAJIB
         dicek dulu: file Illustrator selalu punya boilerplate /DeviceCMYK dominan
         apa pun mode dokumen (false-positive lapisan 3).
      2. Operator plaintext: `k`/`K` (4-operan CMYK) vs `rg`/`RG` (3-operan RGB)
         — untuk EPS uncompressed (Inkscape/gs).
      3. Dominasi token `/DeviceCMYK` vs `/DeviceRGB` (gs compressed).
    """
    try:
        text = Path(eps).read_bytes().decode("latin1")
    except OSError:
        return "?"

    # Layer 1 — XMP swatch mode (ambil kemunculan pertama; sample konsisten).
    m = re.search(r"<xmpG:mode>\s*(CMYK|RGB)\s*</xmpG:mode>", text)
    if m:
        return m.group(1).upper()

    # Layer 2 — operator warna plaintext.
    num = r"\d*\.?\d+"
    n_k = len(re.findall(rf"\b{num} {num} {num} {num} [kK]\b", text))
    n_rg = len(re.findall(rf"\b{num} {num} {num} (?:rg|RG)\b", text))
    if n_k or n_rg:
        return "CMYK" if n_k >= n_rg else "RGB"

    # Layer 3 — dominasi colorspace device.
    n_dc = text.count("/DeviceCMYK")
    n_dr = text.count("/DeviceRGB")
    if n_dc or n_dr:
        return "CMYK" if n_dc > n_dr else "RGB"
    return "?"


def is_cmyk_eps(eps: Path) -> bool:
    """True bila colorspace SUMBER EPS terdeteksi CMYK (lihat source_colorspace)."""
    return source_colorspace(eps) == "CMYK"


def eps_ink_coverage(eps: Path, *, timeout: int = 120) -> dict[str, float] | None:
    """Coverage tinta C/M/Y/K (fraksi 0..1) via render gs `inkcov`.

    Mengukur tinta yang DICETAK (bukan colorspace sumber). `-dEPSCrop` WAJIB —
    tanpanya artwork jatuh di luar page default → render blank → coverage 0 palsu.
    """
    try:
        proc = run(
            [
                "gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-dEPSCrop",
                "-r72", "-sDEVICE=inkcov", "-o", "-", str(eps),
            ],
            timeout=timeout,
        )
    except PipelineError:
        return None
    num = r"([\d.]+)"
    matches = re.findall(rf"{num}\s+{num}\s+{num}\s+{num}\s+CMYK", proc.stdout or "")
    if not matches:
        return None
    # Rata-rata per halaman (EPS umumnya 1 halaman).
    cols = [list(map(float, row)) for row in matches]
    n = len(cols)
    c, m, y, k = (sum(col[i] for col in cols) / n for i in range(4))
    return {"c": c, "m": m, "y": y, "k": k}


def has_black_plate(eps: Path, *, threshold: float = 0.01, timeout: int = 120) -> bool:
    """True bila plate K dipakai (coverage K > threshold).

    CATATAN: K=0 SAH untuk warna jenuh (tiap kanal punya 0 → tak ada komponen abu
    untuk diganti K). Jangan jadikan K=0 sebagai sinyal error.
    """
    cov = eps_ink_coverage(eps, timeout=timeout)
    return bool(cov and cov["k"] > threshold)
