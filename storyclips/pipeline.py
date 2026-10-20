"""De una historia a sus videos: corta en partes en el momento clave, narra, subtitula y monta."""

from __future__ import annotations

import hashlib
import json
import random
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from storyclips.background import Source, pick_segment
from storyclips.ffmpeg import Runner, render_command
from storyclips.models import Audio, Narration, Story
from storyclips.narrate import narrate, write_wav
from storyclips.subtitles import build_ass
from storyclips.text import split_parts
from storyclips.tts import TTS

CARD_S = 2.2  # cuánto se ve «PARTE 1» al empezar y «Parte 2 en el siguiente video» al final
TAIL_S = 2.6  # silencio final de las partes que no son la última, para que se lea la tarjeta


@dataclass(frozen=True)
class PartResult:
    index: int
    total: int
    title: str
    video: Path
    duration_s: float
    background: str


def slugify(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")[:40] or "historia"
    return f"{base}-{hashlib.sha256(title.encode()).hexdigest()[:6]}"


def _with_tail(narration: Narration, seconds: float) -> Narration:
    pad = b"\x00\x00" * int(seconds * narration.audio.sample_rate)
    return Narration(
        Audio(narration.audio.pcm + pad, narration.audio.sample_rate), narration.sentences
    )


def part_title(title: str, index: int, total: int) -> str:
    suffix = f" (Parte {index}/{total})"
    return title[: 100 - len(suffix)] + suffix


def produce(
    story: Story,
    *,
    tts: TTS,
    sources: list[Source],
    out_dir: Path,
    run: Runner,
    rng: random.Random,
    parts: int = 2,
    pause_s: float = 0.25,
) -> list[PartResult]:
    """Genera los videos de la historia. Cada parte menos la última termina en el corte con una
    tarjeta «Parte N en el siguiente video»; la siguiente parte empieza con su «PARTE N»."""
    groups = split_parts(story.text, parts=parts)
    total = len(groups)
    slug = slugify(story.title)
    work = out_dir / "work" / slug
    work.mkdir(parents=True, exist_ok=True)

    results: list[PartResult] = []
    for index, sentences in enumerate(groups, start=1):
        last = index == total
        narration = narrate(sentences, tts, pause_s=pause_s)
        if not last:
            narration = _with_tail(narration, TAIL_S)
        duration = narration.duration_s
        cards = [(0.0, min(CARD_S, duration), f"PARTE {index}")]
        if not last:
            cards.append(
                (max(0.0, duration - CARD_S), duration, f"Parte {index + 1} en el siguiente video")
            )

        voice, ass = work / f"parte{index}.wav", work / f"parte{index}.ass"
        write_wav(narration.audio, voice)
        ass.write_text(build_ass(narration.words, cards=cards), encoding="utf-8")

        segment = pick_segment(sources, duration, rng)
        video = out_dir / f"{slug}_parte{index}.mp4"
        run(
            render_command(
                segment.path, segment.start, duration, voice.resolve(), ass.name, video.resolve()
            ),
            work,
        )
        results.append(
            PartResult(
                index,
                total,
                part_title(story.title, index, total),
                video,
                round(duration, 2),
                segment.path.name,
            )
        )

    (out_dir / f"{slug}.json").write_text(
        json.dumps(
            {
                "title": story.title,
                "parts": [
                    {
                        "index": r.index,
                        "title": r.title,
                        "file": r.video.name,
                        "duration_s": r.duration_s,
                    }
                    for r in results
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return results
