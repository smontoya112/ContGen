"""Línea de comandos: write (historias con LLM), render (video) y batch (las dos cosas)."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import httpx

from storyclips.background import NoBackground, scan_sources
from storyclips.ffmpeg import FfmpegError, analyze_activity, probe_duration, run_ffmpeg
from storyclips.llm import ChatClient, LlmConfig, StoryError, StoryWriter
from storyclips.models import Story
from storyclips.pipeline import produce, slugify
from storyclips.publish import cli as publish_cli
from storyclips.publish.ledger import LedgerError
from storyclips.publish.tiktok import TikTokError
from storyclips.publish.youtube import YouTubeAuthError
from storyclips.tts import TTS, FakeTTS, KokoroTTS, TtsUnavailable


def _write_stories(args: argparse.Namespace, topics: list[str]) -> list[Path]:
    writer = StoryWriter(ChatClient(LlmConfig.from_env()), language=args.language)
    out = Path(args.stories)
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for topic in topics:
        try:
            story = writer.write(topic)
        except (StoryError, httpx.HTTPError) as exc:  # una historia mala no tumba el lote
            print(f"AVISO: sin historia para {topic!r}: {exc}", file=sys.stderr)
            continue
        path = out / f"{slugify(story.title)}.json"
        path.write_text(
            json.dumps(
                {"title": story.title, "text": story.text, "topic": topic},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"historia: {story.title}  ->  {path}")
        paths.append(path)
    if not paths:
        raise StoryError("no se pudo escribir ninguna historia")
    return paths


def _make_tts(args: argparse.Namespace) -> TTS:
    if args.fake_tts:
        return FakeTTS()
    return KokoroTTS(voice=args.voice, lang=args.tts_lang, speed=args.speed)


def _render(args: argparse.Namespace, files: list[Path]) -> None:
    tts = _make_tts(args)
    sources = scan_sources(Path(args.backgrounds), probe_duration, analyze=analyze_activity)
    for src in sources:
        moving = sum(b - a for a, b in src.intervals())
        print(f"fondo {src.path.name}: {moving:.0f} s con movimiento de {src.duration_s:.0f} s")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    made = 0
    for file in files:
        data = json.loads(file.read_text(encoding="utf-8"))
        story = Story(data["title"], data["text"], tuple(data.get("tags", ())))
        try:
            parts = produce(
                story, tts=tts, sources=sources, out_dir=out, run=run_ffmpeg, rng=rng,
                parts=args.parts, allow_loop=args.allow_loop,
            )  # fmt: skip
        except (FfmpegError, ValueError) as exc:  # una historia mala no tumba el lote
            print(f"AVISO: no se montó {file.name}: {exc}", file=sys.stderr)
            continue
        for part in parts:
            made += 1
            print(f"video: {part.video}  ({part.duration_s:.0f} s, fondo {part.background})")
    if not made:
        raise FfmpegError("no se generó ningún video")


def _topics(args: argparse.Namespace) -> list[str]:
    if args.topics_file:
        lines = Path(args.topics_file).read_text(encoding="utf-8").splitlines()
        topics = [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]
    else:
        topics = [args.topic] * args.count if args.topic else []
    if not topics:
        raise ValueError("indica --topic o --topics-file")
    return topics


def _cmd_write(args: argparse.Namespace) -> None:
    _write_stories(args, _topics(args))


def _cmd_render(args: argparse.Namespace) -> None:
    _render(args, [Path(f) for f in args.stories_files])


def _cmd_batch(args: argparse.Namespace) -> None:
    _render(args, _write_stories(args, _topics(args)))


def _common(p: argparse.ArgumentParser, *, write: bool, render: bool) -> None:
    if write:
        p.add_argument("--topic", help="tema de la historia (se repite --count veces)")
        p.add_argument("--count", type=int, default=1)
        p.add_argument("--topics-file", help="un tema por línea (# para comentarios)")
        p.add_argument("--stories", default="stories", help="carpeta de historias")
        p.add_argument("--language", default="español neutro")
    if render:
        p.add_argument("--backgrounds", default="backgrounds", help="tus videos de fondo")
        p.add_argument("--out", default="out")
        p.add_argument("--seed", type=int, default=0)
        p.add_argument(
            "--parts",
            type=int,
            choices=(1, 2),
            default=2,
            help="1 = un solo video; 2 = dos partes con corte",
        )
        p.add_argument(
            "--allow-loop",
            action="store_true",
            help="si no hay tramos con movimiento largos, repite uno corto en bucle (solo pruebas)",
        )
        p.add_argument("--fake-tts", action="store_true", help="tonos en vez de voz (para probar)")
        p.add_argument("--voice", default="ef_dora", help="voz de Kokoro")
        p.add_argument("--tts-lang", default="es", help="idioma de Kokoro (es, en-us…)")
        p.add_argument("--speed", type=float, default=1.1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="storyclips")
    sub = parser.add_subparsers(dest="command", required=True)
    w = sub.add_parser("write", help="escribe historias originales con el LLM")
    _common(w, write=True, render=False)
    w.set_defaults(func=_cmd_write)
    r = sub.add_parser("render", help="convierte historias (.json) en videos verticales")
    r.add_argument("stories_files", nargs="+")
    _common(r, write=False, render=True)
    r.set_defaults(func=_cmd_render)
    b = sub.add_parser("batch", help="escribe y renderiza")
    _common(b, write=True, render=True)
    b.set_defaults(func=_cmd_batch)
    publish_cli.add_parser(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (
        LedgerError,
        TikTokError,
        YouTubeAuthError,
        StoryError,
        NoBackground,
        FfmpegError,
        TtsUnavailable,
        ValueError,
        FileNotFoundError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"ERROR de red con el LLM ({LlmConfig.from_env().base_url}): {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
