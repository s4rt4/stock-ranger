"""ICC profile manager.

Strategi (lihat memory adobe-icc-no-bundle): Adobe SWOP TIDAK di-bundle.
First-run download dari Adobe ke user data dir; fallback ke default_cmyk.icc
Ghostscript (redistributable, SWOP-equivalent).
"""

from __future__ import annotations

import io
import os
import urllib.request
import zipfile
from pathlib import Path

from .util import run

ADOBE_ZIP_URL = (
    "https://download.adobe.com/pub/adobe/iccprofiles/win/"
    "AdobeICCProfilesCS4Win_end-user.zip"
)
_SWOP_MEMBER = "Adobe ICC Profiles (end-user)/CMYK/USWebCoatedSWOP.icc"
SWOP_DESCRIPTION = "U.S. Web Coated (SWOP) v2"

# Lokasi kandidat default_cmyk.icc Ghostscript
_GS_PROFILE_CANDIDATES = [
    "/usr/share/ghostscript/iccprofiles/default_cmyk.icc",
    "/usr/share/ghostscript/*/iccprofiles/default_cmyk.icc",
    "/usr/local/share/ghostscript/iccprofiles/default_cmyk.icc",
]


def user_data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "stock-ranger"


def profiles_dir() -> Path:
    d = user_data_dir() / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def swop_path() -> Path | None:
    """Path SWOP yang sudah di-download user, atau None."""
    p = profiles_dir() / "USWebCoatedSWOP.icc"
    return p if p.exists() else None


def gs_default_cmyk() -> Path | None:
    """Cari default_cmyk.icc bawaan Ghostscript."""
    import glob

    for pattern in _GS_PROFILE_CANDIDATES:
        for hit in glob.glob(pattern):
            if Path(hit).exists():
                return Path(hit)
    return None


def resolve_profile(prefer_swop: bool = True) -> Path | None:
    """Profile CMYK terbaik yang tersedia (SWOP → gs default → None)."""
    if prefer_swop and (p := swop_path()):
        return p
    return gs_default_cmyk()


def download_swop(timeout: int = 60) -> Path:
    """Download bundle Adobe & ekstrak USWebCoatedSWOP.icc ke user dir.

    User memperoleh profile langsung dari Adobe (standalone — sesuai EULA).
    Mengembalikan path profile hasil ekstraksi.
    """
    req = urllib.request.Request(ADOBE_ZIP_URL, headers={"User-Agent": "StockRanger"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        data = resp.read()

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        if _SWOP_MEMBER not in zf.namelist():
            raise RuntimeError("USWebCoatedSWOP.icc tidak ditemukan di bundle Adobe")
        raw = zf.read(_SWOP_MEMBER)

    dest = profiles_dir() / "USWebCoatedSWOP.icc"
    dest.write_bytes(raw)
    return dest


def profile_description(path: Path) -> str | None:
    """Deskripsi ICC profile (verifikasi). None jika gagal dibaca."""
    try:
        from PIL import ImageCms

        prof = ImageCms.getOpenProfile(str(path))
        return ImageCms.getProfileDescription(prof).strip()
    except Exception:
        return None
