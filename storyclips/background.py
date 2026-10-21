"""Videos de fondo: SOLO los tuyos (carpeta `backgrounds/`). Solo se usan tramos CON movimiento."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

VIDEO_SUFFIXES = {".mp4", ".mkv", ".mov", ".webm"}
MIN_LOOP_S = 4.0  # un tramo más corto que esto no vale ni repetido en bucle


class NoBackground(Exception):
    """No hay ningún video de fondo utilizable."""


@dataclass(frozen=True)
class Source:
    path: Path
    duration_s: float
    # Tramos con movimiento (inicio, fin); None = no se analizó y se usa el video entero.
    active: tuple[tuple[float, float], ...] | None = None

    def intervals(self) -> list[tuple[float, float]]:
        return list(self.active) if self.active is not None else [(0.0, self.duration_s)]


@dataclass(frozen=True)
class Segment:
    path: Path
    start: float
    duration_s: float
    loop: bool = False  # el tramo es más corto que lo necesario: se repite en bucle
    clip_s: float | None = None  # duración del tramo que se repite


def scan_sources(
    folder: Path,
    probe: Callable[[Path], float],
    analyze: Callable[[Path, float], list[tuple[float, float]]] | None = None,
) -> list[Source]:
    if not folder.is_dir():
        raise NoBackground(f"no existe la carpeta de fondos: {folder}")
    found = sorted(p for p in folder.iterdir() if p.suffix.lower() in VIDEO_SUFFIXES)
    sources = []
    for path in found:
        duration = probe(path)
        active = tuple(analyze(path, duration)) if analyze else None
        sources.append(Source(path, duration, active))
    if not sources:
        raise NoBackground(f"no hay videos ({', '.join(sorted(VIDEO_SUFFIXES))}) en {folder}")
    return sources


def pick_segment(
    sources: list[Source], need_s: float, rng: random.Random, *, allow_loop: bool = False
) -> Segment:
    """Un tramo de `need_s` segundos seguidos CON movimiento; si no hay, falla (o repite uno corto)."""
    candidates = [(src, a, b) for src in sources for a, b in src.intervals() if b - a >= need_s]
    if candidates:
        src, a, b = rng.choice(candidates)
        return Segment(src.path, round(rng.uniform(a, b - need_s), 3), need_s)

    intervals = [(b - a, src, a) for src in sources for a, b in src.intervals()]
    longest, src, start = max(intervals, key=lambda i: i[0], default=(0.0, None, 0.0))
    if allow_loop and src is not None and longest >= MIN_LOOP_S:
        return Segment(src.path, round(start, 3), need_s, loop=True, clip_s=round(longest, 3))
    total = sum(length for length, _, _ in intervals)
    raise NoBackground(
        f"ningún fondo tiene {need_s:.0f} s seguidos con movimiento (el tramo más largo con movimiento "
        f"dura {longest:.0f} s y en total hay {total:.0f} s). Graba más gameplay en movimiento, o usa "
        "--allow-loop para repetir en bucle un tramo corto (solo para pruebas)"
    )
