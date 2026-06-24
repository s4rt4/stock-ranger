"""Dependency checker — Inkscape, Ghostscript, ExifTool."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .util import run, which

_INSTALL_HINTS = {
    "inkscape": ("Fedora: sudo dnf install inkscape", "Debian: sudo apt install inkscape"),
    "gs": ("Fedora: sudo dnf install ghostscript", "Debian: sudo apt install ghostscript"),
    "exiftool": (
        "Fedora: sudo dnf install perl-Image-ExifTool",
        "Debian: sudo apt install libimage-exiftool-perl",
    ),
}


@dataclass
class DepStatus:
    name: str
    found: bool
    version: str | None
    hint: tuple[str, ...]


def _version(cmd: list[str]) -> str | None:
    try:
        out = run(cmd, timeout=15).stdout.strip()
    except Exception:
        return None
    m = re.search(r"\d+\.\d+(\.\d+)?", out)
    return m.group(0) if m else (out.splitlines()[0] if out else None)


def check_dependencies() -> list[DepStatus]:
    """Cek ketiga tool eksternal yang dibutuhkan pipeline."""
    checks = [
        ("inkscape", ["inkscape", "--version"]),
        ("gs", ["gs", "--version"]),
        ("exiftool", ["exiftool", "-ver"]),
    ]
    result: list[DepStatus] = []
    for name, ver_cmd in checks:
        found = which(name) is not None
        ver = _version(ver_cmd) if found else None
        result.append(DepStatus(name, found, ver, _INSTALL_HINTS[name]))
    return result


def all_present(statuses: list[DepStatus] | None = None) -> bool:
    statuses = statuses or check_dependencies()
    return all(s.found for s in statuses)
