"""Voz en off. `KokoroTTS` es la voz local real (CPU); `FakeTTS` genera tonos para pruebas."""

from __future__ import annotations

import math
import os
import struct
from pathlib import Path
from typing import Protocol

from storyclips.models import Audio

SAMPLE_RATE = 24000


class TTS(Protocol):
    def synthesize(self, text: str) -> Audio: ...


class TtsUnavailable(Exception):
    """Falta el modelo de voz o su dependencia."""


class KokoroTTS:
    """Kokoro (ONNX) en local. Requiere `uv sync --extra tts` y los dos archivos del modelo.

    Los archivos (`kokoro-v1.0.onnx` y `voices-v1.0.bin`) los descargas tú desde la página oficial del
    proyecto kokoro-onnx; rutas en STORYCLIPS_KOKORO_MODEL y STORYCLIPS_KOKORO_VOICES.
    """

    def __init__(
        self,
        model_path: str | None = None,
        voices_path: str | None = None,
        *,
        voice: str = "af_heart",
        lang: str = "en-us",
        speed: float = 1.0,
    ) -> None:
        model = Path(
            model_path or os.environ.get("STORYCLIPS_KOKORO_MODEL", "models/kokoro-v1.0.onnx")
        )
        voices = Path(
            voices_path or os.environ.get("STORYCLIPS_KOKORO_VOICES", "models/voices-v1.0.bin")
        )
        for path in (model, voices):
            if not path.exists():
                raise TtsUnavailable(f"falta {path}: descarga el modelo de Kokoro (ver README)")
        try:
            from kokoro_onnx import Kokoro
        except ImportError as exc:
            raise TtsUnavailable("falta kokoro-onnx: corre `uv sync --extra tts`") from exc
        self._kokoro = Kokoro(str(model), str(voices))
        self._voice, self._lang, self._speed = voice, lang, speed

    def synthesize(self, text: str) -> Audio:
        samples, rate = self._kokoro.create(
            text, voice=self._voice, speed=self._speed, lang=self._lang
        )
        import numpy as np

        pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
        return Audio(pcm, int(rate))


class FakeTTS:
    """Tono cuya duración es proporcional a las palabras (≈2,5 palabras/s): determinista y sin modelo."""

    def __init__(self, words_per_second: float = 2.5) -> None:
        self._wps = words_per_second

    def synthesize(self, text: str) -> Audio:
        seconds = max(0.4, len(text.split()) / self._wps)
        n = int(seconds * SAMPLE_RATE)
        pcm = b"".join(
            struct.pack("<h", int(3000 * math.sin(2 * math.pi * 220 * i / SAMPLE_RATE)))
            for i in range(n)
        )
        return Audio(pcm, SAMPLE_RATE)
