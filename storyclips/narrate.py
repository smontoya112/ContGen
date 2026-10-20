"""Voz en off de un fragmento: una síntesis por frase, pausas entre frases y tiempo por palabra."""

from __future__ import annotations

import wave
from collections.abc import Sequence
from pathlib import Path

from storyclips.models import Audio, Narration, Sentence, Word
from storyclips.tts import TTS


def _silence(seconds: float, rate: int) -> bytes:
    return b"\x00\x00" * int(seconds * rate)


def word_timings(sentence: str, start: float, end: float) -> tuple[Word, ...]:
    """Reparte la duración de la frase entre sus palabras según su longitud en caracteres."""
    words = sentence.split()
    weights = [len(w) + 1 for w in words]  # +1: cada palabra arrastra su pausa mínima
    total = sum(weights)
    cursor, timed = start, []
    for word, weight in zip(words, weights, strict=True):
        span = (end - start) * weight / total
        timed.append(Word(word, round(cursor, 3), round(cursor + span, 3)))
        cursor += span
    return tuple(timed)


def narrate(sentences: Sequence[str], tts: TTS, *, pause_s: float = 0.25) -> Narration:
    if not sentences:
        raise ValueError("no hay frases que narrar")
    chunks: list[bytes] = []
    timed: list[Sentence] = []
    rate: int | None = None
    cursor = 0.0
    for text in sentences:
        audio = tts.synthesize(text)
        rate = rate or audio.sample_rate
        if audio.sample_rate != rate:
            raise ValueError("el TTS cambió de frecuencia de muestreo a mitad del fragmento")
        start, end = cursor, cursor + audio.duration_s
        timed.append(Sentence(text, round(start, 3), round(end, 3), word_timings(text, start, end)))
        chunks += [audio.pcm, _silence(pause_s, rate)]
        cursor = end + pause_s
    return Narration(Audio(b"".join(chunks), rate or 0), tuple(timed))


def write_wav(audio: Audio, path: Path) -> None:
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(audio.sample_rate)
        out.writeframes(audio.pcm)
