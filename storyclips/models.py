"""Tipos compartidos."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Story:
    title: str
    text: str
    tags: tuple[str, ...] = ()  # etiquetas propias de la historia (sin #)


@dataclass(frozen=True)
class Audio:
    """Audio mono PCM de 16 bits."""

    pcm: bytes
    sample_rate: int

    @property
    def duration_s(self) -> float:
        return len(self.pcm) / 2 / self.sample_rate


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class Sentence:
    text: str
    start: float
    end: float
    words: tuple[Word, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Narration:
    """Voz en off completa de un fragmento: audio y el tiempo de cada frase y palabra."""

    audio: Audio
    sentences: tuple[Sentence, ...]

    @property
    def duration_s(self) -> float:
        return self.audio.duration_s

    @property
    def words(self) -> tuple[Word, ...]:
        return tuple(w for s in self.sentences for w in s.words)
