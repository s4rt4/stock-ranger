"""Build output ZIP dari pasangan EPS + JPG."""

from __future__ import annotations

import zipfile
from pathlib import Path


def build_zip(files: list[Path], zip_path: Path) -> Path:
    """Bungkus daftar file ke satu ZIP (disimpan flat, tanpa struktur folder)."""
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            f = Path(f)
            if f.exists():
                zf.write(f, arcname=f.name)
    return zip_path


def build_pair_zip(eps: Path, jpg: Path, out_dir: Path, name: str | None = None) -> Path:
    """Satu ZIP per pasangan EPS+JPG."""
    stem = name or Path(eps).stem
    return build_zip([eps, jpg], Path(out_dir) / f"{stem}.zip")
