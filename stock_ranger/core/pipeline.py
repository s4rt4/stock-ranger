"""Orchestrator pipeline: SVG → EPS + JPG + metadata → ZIP.

Headless & dapat diuji via CLI (lihat __main__). UI memanggil lewat worker thread.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from . import eps_generator, jpg_generator, metadata_writer, profile_manager, svg_parser, zip_builder
from .models import JobResult, JpgMode, Metadata, OutputSettings

# Callback log: (pesan) -> None
LogFn = Callable[[str], None]
# Callback progres per-file: (file_index, total_files, stage, stage_total) -> None
ProgressFn = Callable[[int, int, int, int], None]

_STAGES = 5  # validate, eps, jpg, metadata, zip


def _noop_log(_msg: str) -> None:
    pass


def process_one(
    svg: Path,
    meta: Metadata,
    settings: OutputSettings,
    *,
    index: int = 0,
    total: int = 1,
    log: LogFn = _noop_log,
    progress: ProgressFn | None = None,
    manual_jpg: Path | None = None,
) -> JobResult:
    """Proses satu SVG menjadi EPS+JPG ber-metadata + ZIP."""
    svg = Path(svg)
    result = JobResult(source=svg)
    out_dir = Path(settings.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    icc = settings.icc_profile or profile_manager.resolve_profile()

    def step(stage: int, msg: str) -> None:
        log(f"[{svg.name}] {msg}")
        if progress:
            progress(index, total, stage, _STAGES)

    try:
        # 1. Validate
        step(1, "validasi SVG…")
        info = svg_parser.parse(svg)
        if not info.valid:
            result.error = info.error
            return result
        result.warnings.extend(info.warnings)

        # 2. EPS 10 CMYK
        step(2, "generate EPS 10 CMYK…")
        eps = out_dir / f"{svg.stem}.eps"
        eps_generator.generate(svg, eps, icc_profile=icc)
        if not eps_generator.is_cmyk_eps(eps):
            result.warnings.append("EPS tidak terdeteksi CMYK (cek profile)")
        result.eps_path = eps

        # 3. JPG preview
        step(3, "generate JPG preview…")
        jpg = out_dir / f"{svg.stem}.jpg"
        if settings.jpg_mode == JpgMode.MANUAL and manual_jpg:
            jpg_generator.import_existing(manual_jpg, jpg, quality=settings.jpg_quality)
        elif settings.jpg_mode == JpgMode.MANUAL:
            result.warnings.append("Mode manual tapi JPG tak ditemukan — rasterize otomatis")
            jpg_generator.rasterize(
                svg, jpg,
                width=settings.jpg_width, height=settings.jpg_height,
                dpi=settings.dpi, quality=settings.jpg_quality,
            )
        else:
            jpg_generator.rasterize(
                svg, jpg,
                width=settings.jpg_width, height=settings.jpg_height,
                dpi=settings.dpi, quality=settings.jpg_quality,
            )
        result.jpg_path = jpg

        # 4. Embed metadata ke EPS & JPG
        step(4, "embed metadata XMP/IPTC…")
        metadata_writer.embed(eps, meta)
        metadata_writer.embed(jpg, meta)

        # 5. ZIP
        step(5, "build ZIP…")
        if settings.zip_per_pair:
            result.zip_path = zip_builder.build_pair_zip(eps, jpg, out_dir)
        result.ok = True
        log(f"[{svg.name}] ✓ selesai")
    except Exception as e:  # noqa: BLE001 — kumpulkan error per-file, jangan hentikan batch
        result.error = str(e)
        log(f"[{svg.name}] ✗ {e}")
    return result


def process_batch(
    svgs: list[Path],
    meta: Metadata,
    settings: OutputSettings,
    *,
    log: LogFn = _noop_log,
    progress: ProgressFn | None = None,
    manual_jpgs: dict[str, Path] | None = None,
) -> list[JobResult]:
    """Proses banyak SVG. Metadata sama untuk semua (shared).

    manual_jpgs: mapping stem→path JPG existing untuk mode MANUAL (per file).
    """
    manual_jpgs = manual_jpgs or {}
    results: list[JobResult] = []
    total = len(svgs)
    for i, svg in enumerate(svgs):
        results.append(
            process_one(
                svg, meta, settings,
                index=i, total=total, log=log, progress=progress,
                manual_jpg=manual_jpgs.get(Path(svg).stem),
            )
        )
    # Batch ZIP gabungan jika diminta
    if not settings.zip_per_pair and any(r.ok for r in results):
        files: list[Path] = []
        for r in results:
            if r.eps_path:
                files.append(r.eps_path)
            if r.jpg_path:
                files.append(r.jpg_path)
        out_dir = Path(settings.out_dir).expanduser()
        bundle = zip_builder.build_zip(files, out_dir / "StockRanger_batch.zip")
        log(f"Batch ZIP: {bundle.name} ({len(files)} file)")
    return results


if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Stock Ranger pipeline (CLI test)")
    ap.add_argument("svg", nargs="+", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("./out"))
    ap.add_argument("--title", default="")
    ap.add_argument("--desc", default="")
    ap.add_argument("--keywords", default="")
    args = ap.parse_args()

    md = Metadata(
        title=args.title,
        description=args.desc,
        keywords=[k.strip() for k in args.keywords.split(",") if k.strip()],
    )
    cfg = OutputSettings(out_dir=args.out)
    res = process_batch(args.svg, md, cfg, log=lambda m: print(m))
    ok = sum(1 for r in res if r.ok)
    print(f"\n{ok}/{len(res)} sukses")
    sys.exit(0 if ok == len(res) else 1)
