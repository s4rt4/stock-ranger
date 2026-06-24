"""Helper subprocess + exception bersama."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class PipelineError(RuntimeError):
    """Error pada salah satu tahap pipeline."""


def which(name: str) -> str | None:
    """Lokasi executable di PATH, atau None."""
    return shutil.which(name)


def run(cmd: list[str], *, timeout: int = 120, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Jalankan command eksternal, raise PipelineError jika gagal."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
        )
    except FileNotFoundError as e:
        raise PipelineError(f"Executable tidak ditemukan: {cmd[0]}") from e
    except subprocess.TimeoutExpired as e:
        raise PipelineError(f"Timeout ({timeout}s): {cmd[0]}") from e

    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-6:]
        raise PipelineError(
            f"{cmd[0]} gagal (exit {proc.returncode}):\n" + "\n".join(tail)
        )
    return proc
