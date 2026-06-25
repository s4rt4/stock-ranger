"""Embed metadata XMP/IPTC ke EPS & JPG via ExifTool.

Mapping (sama seperti Adobe Bridge):
  Title       → XMP-dc:Title       + IPTC:ObjectName
  Description → XMP-dc:Description  + IPTC:Caption-Abstract
  Keywords    → XMP-dc:Subject     + IPTC:Keywords
"""

from __future__ import annotations

from pathlib import Path

from .models import Metadata
from .util import run


def _build_args(meta: Metadata) -> list[str]:
    args: list[str] = ["-overwrite_original", "-codedcharacterset=utf8"]
    if meta.title:
        args += [f"-XMP-dc:Title={meta.title}", f"-IPTC:ObjectName={meta.title}"]
    if meta.description:
        args += [
            f"-XMP-dc:Description={meta.description}",
            f"-IPTC:Caption-Abstract={meta.description}",
        ]
    # Reset lalu tambah keywords (hindari duplikasi saat re-run)
    args += ["-XMP-dc:Subject=", "-IPTC:Keywords="]
    for kw in meta.cleaned_keywords():
        args += [f"-XMP-dc:Subject+={kw}", f"-IPTC:Keywords+={kw}"]
    return args


def embed(target: Path, meta: Metadata, *, timeout: int = 60) -> Path:
    """Embed metadata ke satu file (EPS atau JPG)."""
    target = Path(target)
    args = _build_args(meta)
    if len(args) <= 4:  # cuma flag default, tidak ada metadata berarti
        return target
    run(["exiftool", *args, str(target)], timeout=timeout)
    return target


def read_back(target: Path) -> dict[str, str]:
    """Baca metadata utama untuk verifikasi."""
    proc = run(
        [
            "exiftool",
            "-s",
            "-XMP-dc:Title",
            "-XMP-dc:Description",
            "-XMP-dc:Subject",
            str(target),
        ]
    )
    out: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def read_metadata(target: Path) -> Metadata:
    """Baca Title/Description/Keywords dari file (EPS/JPG/dll) -> Metadata.

    Pakai output JSON exiftool (robust untuk list keyword). Coba XMP dulu,
    fallback IPTC. Metadata kosong bila file tak terbaca / tanpa metadata.
    """
    import json

    try:
        proc = run([
            "exiftool", "-j",
            "-XMP-dc:Title", "-IPTC:ObjectName",
            "-XMP-dc:Description", "-IPTC:Caption-Abstract",
            "-XMP-dc:Subject", "-IPTC:Keywords",
            str(target),
        ])
        data = json.loads(proc.stdout)[0]
    except Exception:  # noqa: BLE001 - file tak terbaca / no metadata
        return Metadata()

    def as_list(v) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return [s.strip() for s in str(v).split(",") if s.strip()]

    title = str(data.get("Title") or data.get("ObjectName") or "")
    desc = str(data.get("Description") or data.get("Caption-Abstract") or "")
    keywords = as_list(data.get("Subject")) or as_list(data.get("Keywords"))
    return Metadata(title=title, description=desc, keywords=keywords)
