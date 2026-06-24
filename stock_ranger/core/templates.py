"""Metadata template — simpan/muat preset untuk batch sejenis (JSON di user dir)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import Metadata
from .profile_manager import user_data_dir


def templates_dir() -> Path:
    d = user_data_dir() / "templates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", name.strip()).strip("_")
    return s or "template"


def list_templates() -> list[str]:
    return sorted(p.stem for p in templates_dir().glob("*.json"))


def save_template(name: str, meta: Metadata) -> Path:
    path = templates_dir() / f"{_slug(name)}.json"
    payload = {
        "name": name,
        "title": meta.title,
        "description": meta.description,
        "keywords": meta.cleaned_keywords(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return path


def load_template(name: str) -> Metadata:
    path = templates_dir() / f"{_slug(name)}.json"
    data = json.loads(path.read_text())
    return Metadata(
        title=data.get("title", ""),
        description=data.get("description", ""),
        keywords=list(data.get("keywords", [])),
    )


def delete_template(name: str) -> None:
    path = templates_dir() / f"{_slug(name)}.json"
    path.unlink(missing_ok=True)
