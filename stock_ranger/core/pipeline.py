"""Orchestrator pipeline: SVG → EPS + JPG + metadata → ZIP.

Headless & dapat diuji via CLI (lihat __main__). UI memanggil lewat worker thread.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from . import eps_generator, jpg_generator, metadata_writer, profile_manager, svg_parser, zip_builder
from .models import ExportTarget, JobResult, JpgMode, Metadata, OutputMode, OutputSettings

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


def _safe_name(name: str) -> str:
    """Nama folder aman dari nama target."""
    return re.sub(r"[^\w.-]+", "_", name).strip("_") or "target"


def process_one_multi(
    svg: Path,
    meta: Metadata,
    targets: list[ExportTarget],
    settings: OutputSettings,
    *,
    index: int = 0,
    total: int = 1,
    log: LogFn = _noop_log,
    progress: ProgressFn | None = None,
    manual_jpg: Path | None = None,
) -> JobResult:
    """Satu SVG → export ke BANYAK target sekaligus.

    EPS dibuat SEKALI (identik untuk semua target) lalu disalin per target.
    JPG dirender per kombinasi (rule,value,quality) unik (dedupe). Paket per
    output_mode target. Output ke subfolder out_dir/<target>/.
    """
    svg = Path(svg)
    result = JobResult(source=svg)
    base = Path(settings.out_dir).expanduser()
    icc = settings.icc_profile or profile_manager.resolve_profile()
    active = [t for t in targets if t.enabled]
    if not active:
        result.error = "Tidak ada target aktif"
        return result

    def step(stage: int, msg: str) -> None:
        log(f"[{svg.name}] {msg}")
        if progress:
            progress(index, total, stage, _STAGES)

    try:
        step(1, "validasi SVG…")
        info = svg_parser.parse(svg)
        if not info.valid:
            result.error = info.error
            return result
        result.warnings.extend(info.warnings)

        with tempfile.TemporaryDirectory(prefix="stockranger_multi_") as td:
            tdp = Path(td)

            # 1. EPS sekali (metadata via on_raw)
            step(2, "generate EPS 10 CMYK + metadata…")
            eps_master = tdp / f"{svg.stem}.eps"
            eps_generator.generate(
                svg, eps_master, icc_profile=icc,
                on_raw=lambda raw: metadata_writer.embed(raw, meta),
            )
            if not eps_generator.is_cmyk_eps(eps_master):
                result.warnings.append("EPS tidak terdeteksi CMYK (cek profile)")

            # 2. JPG cache per (rule,value,quality) unik
            jpg_cache: dict[tuple, Path] = {}

            def get_jpg(t: ExportTarget) -> Path:
                key = (t.jpg_rule, t.jpg_value, t.jpg_quality)
                if key not in jpg_cache:
                    jp = tdp / f"{svg.stem}__{len(jpg_cache)}.jpg"
                    if settings.jpg_mode == JpgMode.MANUAL and manual_jpg:
                        jpg_generator.import_existing(
                            manual_jpg, jp, rule=t.jpg_rule,
                            value=t.jpg_value, quality=t.jpg_quality,
                        )
                    else:
                        if settings.jpg_mode == JpgMode.MANUAL:
                            result.warnings.append("Mode manual tapi JPG tak ada — rasterize")
                        jpg_generator.rasterize(
                            svg, jp, rule=t.jpg_rule, value=t.jpg_value,
                            dpi=settings.dpi, quality=t.jpg_quality,
                        )
                    metadata_writer.embed(jp, meta)
                    jpg_cache[key] = jp
                return jpg_cache[key]

            # 3. Distribusi per target
            step(3, f"paket ke {len(active)} target…")
            for t in active:
                sub = base / _safe_name(t.name)
                sub.mkdir(parents=True, exist_ok=True)
                eps_dest = sub / f"{svg.stem}.eps"
                shutil.copy2(eps_master, eps_dest)

                if t.needs_jpg:
                    jpg_dest = sub / f"{svg.stem}.jpg"
                    shutil.copy2(get_jpg(t), jpg_dest)
                    if t.output_mode == OutputMode.PAIR_ZIP:
                        z = zip_builder.build_pair_zip(eps_dest, jpg_dest, sub)
                        eps_dest.unlink(missing_ok=True)
                        jpg_dest.unlink(missing_ok=True)
                        result.outputs[t.name] = [z]
                    else:  # PAIR_LOOSE
                        result.outputs[t.name] = [eps_dest, jpg_dest]
                else:  # EPS_ONLY
                    result.outputs[t.name] = [eps_dest]
                log(f"[{svg.name}] → {t.name}: {', '.join(p.name for p in result.outputs[t.name])}")

        # back-compat: isi field tunggal dari target pertama
        first = result.outputs[active[0].name]
        for p in first:
            if p.suffix == ".eps":
                result.eps_path = p
            elif p.suffix == ".jpg":
                result.jpg_path = p
            elif p.suffix == ".zip":
                result.zip_path = p
        result.ok = True
        log(f"[{svg.name}] ✓ selesai ({len(active)} target)")
    except Exception as e:  # noqa: BLE001
        result.error = str(e)
        log(f"[{svg.name}] ✗ {e}")
    return result


def process_batch_multi(
    svgs: list[Path],
    meta: Metadata,
    targets: list[ExportTarget],
    settings: OutputSettings,
    *,
    log: LogFn = _noop_log,
    progress: ProgressFn | None = None,
    manual_jpgs: dict[str, Path] | None = None,
) -> list[JobResult]:
    """Banyak SVG → masing-masing di-export ke semua target aktif."""
    manual_jpgs = manual_jpgs or {}
    results: list[JobResult] = []
    total = len(svgs)
    for i, svg in enumerate(svgs):
        results.append(
            process_one_multi(
                svg, meta, targets, settings,
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
