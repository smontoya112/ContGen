"""Videos de fondo: SOLO los tuyos (carpeta `backgrounds/`). De cada uno se corta un tramo al azar."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

VIDEO_SUFFIXES = {".mp4", ".mkv", ".mov", ".webm"}


class NoBackground(Exception):
    """No hay ningún video de fondo lo bastante largo."""


@dataclass(frozen=True)
class Source:
    path: Path
    duration_s: float


@dataclass(frozen=True)
class Segment:
    path: Path
    start: float
    duration_s: float


def scan_sources(folder: Path, probe: Callable[[Path], float]) -> list[Source]:
    if not folder.is_dir():
        raise NoBackground(f"no existe la carpeta de fondos: {folder}")
    found = sorted(p for p in folder.iterdir() if p.suffix.lower() in VIDEO_SUFFIXES)
    sources = [Source(p, probe(p)) for p in found]
    if not sources:
        raise NoBackground(f"no hay videos ({', '.join(sorted(VIDEO_SUFFIXES))}) en {folder}")
    return sources


def pick_segment(sources: list[Source], need_s: float, rng: random.Random) -> Segment:
    """Un tramo de `need_s` segundos de un video al azar con duración suficiente."""
    fitting = [s for s in sources if s.duration_s >= need_s]
    if not fitting:
        longest = max((s.duration_s for s in sources), default=0.0)
        raise NoBackground(
            f"ningún fondo dura {need_s:.0f} s (el más largo dura {longest:.0f} s): añade videos más largos"
        )
    source = rng.choice(fitting)
    start = rng.uniform(0, source.duration_s - need_s)
    return Segment(source.path, round(start, 3), need_s)
