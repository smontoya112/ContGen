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
    return [
        ffmpeg, "-y",
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
