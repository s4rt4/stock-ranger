"""Preset Export Target per microstock — default + simpan/muat JSON.

Disimpan di ~/.local/share/stock-ranger/targets.json. Nilai default di bawah
adalah TITIK AWAL yang bisa diedit user (tiap agensi bisa ubah kebijakan).
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import ExportTarget, JpgSizeRule, OutputMode

_CONFIG_DIR = Path.home() / ".local" / "share" / "stock-ranger"
_TARGETS_FILE = _CONFIG_DIR / "targets.json"


def default_targets() -> list[ExportTarget]:
    """Preset awal mewakili 3 kelompok kebijakan upload."""
    return [
        ExportTarget("Shutterstock", OutputMode.EPS_ONLY,
                     JpgSizeRule.LONGEST_SIDE, 4000, enabled=True),
        ExportTarget("Adobe Stock", OutputMode.PAIR_LOOSE,
                     JpgSizeRule.LONGEST_SIDE, 4000, enabled=True),
        ExportTarget("Freepik", OutputMode.PAIR_ZIP,
                     JpgSizeRule.LONGEST_SIDE, 4000, enabled=False),
    ]


def _to_dict(t: ExportTarget) -> dict:
    return {
        "name": t.name,
        "output_mode": t.output_mode.value,
        "jpg_rule": t.jpg_rule.value,
        "jpg_value": t.jpg_value,
        "jpg_quality": t.jpg_quality,
        "enabled": t.enabled,
    }


def _from_dict(d: dict) -> ExportTarget:
    return ExportTarget(
        name=d["name"],
        output_mode=OutputMode(d.get("output_mode", "pair_zip")),
        jpg_rule=JpgSizeRule(d.get("jpg_rule", "longest_side")),
        jpg_value=int(d.get("jpg_value", 4000)),
        jpg_quality=int(d.get("jpg_quality", 92)),
        enabled=bool(d.get("enabled", True)),
    )


def load_targets() -> list[ExportTarget]:
    """Muat dari disk; jika belum ada / korup → default (dan simpan)."""
    try:
        data = json.loads(_TARGETS_FILE.read_text())
        targets = [_from_dict(d) for d in data]
        if targets:
            return targets
    except (OSError, ValueError, KeyError):
        pass
    targets = default_targets()
    save_targets(targets)
    return targets


def save_targets(targets: list[ExportTarget]) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _TARGETS_FILE.write_text(json.dumps([_to_dict(t) for t in targets], indent=2))
