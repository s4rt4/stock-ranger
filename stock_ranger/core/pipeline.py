"""Orchestrator pipeline: SVG → EPS + JPG + metadata → ZIP.

Headless & dapat diuji via CLI (lihat __main__). UI memanggil lewat worker thread.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from . import eps_generator, jpg_generator, metadata_writer, profile_manager, svg_parser, zip_builder
from .models import JobResult, JpgMode, Metadata, OutputMode, OutputSettings

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

        # 2. EPS 10 CMYK — metadata XMP di-embed ke EPS MENTAH via on_raw hook
        #    (exiftool menolak XMP ke EPS ber-header Illustrator → harus pre-spoof)
        step(2, "generate EPS 10 CMYK + metadata…")
        eps = out_dir / f"{svg.stem}.eps"
        eps_generator.generate(
            svg, eps, icc_profile=icc,
            on_raw=lambda raw: metadata_writer.embed(raw, meta),
        )
        if not eps_generator.is_cmyk_eps(eps):
            result.warnings.append("EPS tidak terdeteksi CMYK (cek profile)")
        result.eps_path = eps

        # 3. JPG (lewati untuk mode EPS_ONLY / Kel.1)
        jpg: Path | None = None
        if settings.needs_jpg:
            step(3, "generate JPG…")
            jpg = out_dir / f"{svg.stem}.jpg"
            if settings.jpg_mode == JpgMode.MANUAL and manual_jpg:
                jpg_generator.import_existing(
                    manual_jpg, jpg,
                    rule=settings.jpg_rule, value=settings.jpg_value,
                    quality=settings.jpg_quality,
                )
            else:
                if settings.jpg_mode == JpgMode.MANUAL:
                    result.warnings.append("Mode manual tapi JPG tak ditemukan — rasterize otomatis")
                jpg_generator.rasterize(
                    svg, jpg,
                    rule=settings.jpg_rule, value=settings.jpg_value,
                    dpi=settings.dpi, quality=settings.jpg_quality,
                )
            result.jpg_path = jpg

        # 4. Embed metadata ke JPG (EPS sudah di-embed di step 2 via on_raw) — SAMA
        if jpg is not None:
            step(4, "embed metadata XMP/IPTC…")
            metadata_writer.embed(jpg, meta)

        # 5. Paket sesuai output_mode
        step(5, "paket output…")
        if settings.output_mode == OutputMode.PAIR_ZIP and jpg is not None:
            result.zip_path = zip_builder.build_pair_zip(eps, jpg, out_dir)
        # EPS_ONLY & PAIR_LOOSE → file dibiarkan loose di out_dir
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
