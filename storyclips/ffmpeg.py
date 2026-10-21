"""Comandos de FFmpeg/ffprobe (constructores puros) y el ejecutor."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

_SAFE_NAME = re.compile(r"^[\w.\-]+$")

Runner = Callable[[list[str], Path | None], None]


class FfmpegError(Exception):
    """FFmpeg no está disponible o falló."""


def probe_command(path: Path, *, ffprobe: str = "ffprobe") -> list[str]:
    return [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        os.fspath(path),
    ]


def parse_duration(output: str) -> float:
    try:
        return float(json.loads(output)["format"]["duration"])
    except (ValueError, KeyError, TypeError) as exc:
        raise FfmpegError(f"salida de ffprobe inesperada: {output[:120]!r}") from exc


def render_command(
    background: Path,
    start: float,
    duration: float,
    voice: Path,
    ass_name: str,
    out: Path,
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    loop: bool = False,
    ffmpeg: str = "ffmpeg",
) -> list[str]:
    """Fondo recortado a vertical + voz en off + subtítulos quemados.

    `ass_name` es un nombre simple (se ejecuta con `cwd` en su carpeta): así no hay que escapar rutas
    de Windows dentro del filtro `subtitles`. El audio del juego se descarta: solo suena la voz.
    """
    if not _SAFE_NAME.match(ass_name):
        raise ValueError(f"nombre de subtítulos no permitido: {ass_name!r}")
    video = (
        f"[0:v]crop=ih*{width}/{height}:ih,scale={width}:{height},setsar=1,fps={fps},"
        f"subtitles={ass_name}[v]"
    )
    repeat = ["-stream_loop", "-1"] if loop else []  # el fondo es un clip corto que se repite
    return [
        ffmpeg, "-y", *repeat,
        "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", os.fspath(background),
        "-i", os.fspath(voice),
        "-filter_complex", video, "-map", "[v]", "-map", "1:a",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", os.fspath(out),
    ]  # fmt: skip


def run_ffmpeg(cmd: list[str], cwd: Path | None = None) -> None:
    if shutil.which(cmd[0]) is None:
        raise FfmpegError(f"no encuentro '{cmd[0]}': instala FFmpeg (winget install Gyan.FFmpeg)")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise FfmpegError(f"{cmd[0]} falló ({result.returncode}): {result.stderr[-400:]}")


def probe_duration(path: Path, *, ffprobe: str = "ffprobe") -> float:
    if shutil.which(ffprobe) is None:
        raise FfmpegError(f"no encuentro '{ffprobe}': instala FFmpeg")
    result = subprocess.run(probe_command(path, ffprobe=ffprobe), capture_output=True, text=True)
    if result.returncode != 0:
        raise FfmpegError(f"ffprobe falló con {path.name}: {result.stderr[-200:]}")
    return parse_duration(result.stdout)


# --------------------------------------------------------------------------- movimiento del fondo

_FREEZE_START = re.compile(r"freeze_start:\s*([\d.]+)")
_FREEZE_END = re.compile(r"freeze_end:\s*([\d.]+)")


def freezedetect_command(
    path: Path, *, noise_db: float = -50.0, min_freeze_s: float = 1.0, ffmpeg: str = "ffmpeg"
) -> list[str]:
    """Detecta los tramos CONGELADOS del video (menú de pausa, pantalla quieta). Analiza a baja resolución."""
    video = f"scale=320:-2,freezedetect=n={noise_db}dB:d={min_freeze_s}"
    return [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-i",
        os.fspath(path),
        "-vf",
        video,
        "-an",
        "-f",
        "null",
        "-",
    ]


def parse_freezes(stderr: str, duration: float) -> list[tuple[float, float]]:
    """(inicio, fin) de cada tramo congelado; uno sin fin dura hasta el final del video."""
    freezes: list[tuple[float, float]] = []
    start: float | None = None
    for line in stderr.splitlines():
        if match := _FREEZE_START.search(line):
            start = float(match.group(1))
        elif (match := _FREEZE_END.search(line)) and start is not None:
            freezes.append((start, float(match.group(1))))
            start = None
    if start is not None:
        freezes.append((start, duration))
    return freezes


def active_intervals(
    duration: float, freezes: list[tuple[float, float]], *, min_len: float = 3.0
) -> list[tuple[float, float]]:
    """Tramos CON movimiento: lo que queda al quitar los congelados, de al menos `min_len` segundos."""
    active: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in sorted(freezes):
        if start - cursor >= min_len:
            active.append((round(cursor, 3), round(start, 3)))
        cursor = max(cursor, end)
    if duration - cursor >= min_len:
        active.append((round(cursor, 3), round(duration, 3)))
    return active


def clip_command(
    background: Path, start: float, length: float, out: Path, *, ffmpeg: str = "ffmpeg"
) -> list[str]:
    """Corta un clip corto (recodificado, para poder repetirlo en bucle sin saltos de fotograma clave)."""
    return [
        ffmpeg, "-y", "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", os.fspath(background),
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        os.fspath(out),
    ]  # fmt: skip


def analyze_activity(
    path: Path,
    duration: float,
    *,
    run_ffmpeg_stderr: Callable[[list[str]], str] | None = None,
    min_len: float = 3.0,
) -> list[tuple[float, float]]:
    """Tramos con movimiento de un video. El resultado se guarda junto al video (`.activity.json`) y se
    reutiliza mientras el archivo no cambie."""
    cache = path.with_name(path.name + ".activity.json")
    stat = path.stat()
    key = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "min_len": min_len}
    try:
        cached = json.loads(cache.read_text(encoding="utf-8"))
        if cached.get("key") == key:
            return [tuple(i) for i in cached["intervals"]]
    except (OSError, ValueError, KeyError):
        pass

    def default_run(cmd: list[str]) -> str:
        if shutil.which(cmd[0]) is None:
            raise FfmpegError(f"no encuentro '{cmd[0]}': instala FFmpeg")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise FfmpegError(
                f"no se pudo analizar el movimiento de {path.name}: {result.stderr[-200:]}"
            )
        return result.stderr

    stderr = (run_ffmpeg_stderr or default_run)(freezedetect_command(path))
    intervals = active_intervals(duration, parse_freezes(stderr, duration), min_len=min_len)
    try:
        cache.write_text(json.dumps({"key": key, "intervals": intervals}), encoding="utf-8")
    except OSError:
        pass  # carpeta de solo lectura: se recalcula la próxima vez
    return intervals
