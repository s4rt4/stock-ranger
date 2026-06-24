"""Auto-pair EPS + JPG berdasarkan nama file (tanpa ekstensi)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Pair:
    stem: str
    eps: Path | None = None
    jpg: Path | None = None

    @property
    def complete(self) -> bool:
        return self.eps is not None and self.jpg is not None


@dataclass
class PairResult:
    pairs: list[Pair] = field(default_factory=list)
    unpaired: list[Path] = field(default_factory=list)

    @property
    def complete_pairs(self) -> list[Pair]:
        return [p for p in self.pairs if p.complete]


_JPG_EXT = {".jpg", ".jpeg"}


def pair_directory(directory: Path) -> PairResult:
    """Scan folder, pasangkan .eps dengan .jpg/.jpeg bernama sama."""
    directory = Path(directory)
    by_stem: dict[str, Pair] = {}

    for f in sorted(directory.iterdir()):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext == ".eps":
            by_stem.setdefault(f.stem, Pair(f.stem)).eps = f
        elif ext in _JPG_EXT:
            by_stem.setdefault(f.stem, Pair(f.stem)).jpg = f

    result = PairResult()
    for pair in by_stem.values():
        result.pairs.append(pair)
        if not pair.complete:
            result.unpaired.append(pair.eps or pair.jpg)  # type: ignore[arg-type]
    return result
