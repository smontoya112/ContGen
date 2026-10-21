"""Subcomandos `storyclips publish ...`: enqueue, run, status y auth-youtube."""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime, time
from pathlib import Path

from storyclips.publish.ledger import Ledger
from storyclips.publish.metadata import build_metadata, load_sidecar
from storyclips.publish.runner import PublishConfig, run
from storyclips.publish.schedule import DEFAULT_TZ, next_slots, parse_local
from storyclips.publish.tiktok import HttpTikTokClient, TikTokClient
from storyclips.publish.youtube import (
    GoogleYouTubeClient,
    YouTubeAuthError,
    YouTubeClient,
    authorize,
)

HOME = Path.home() / ".storyclips"
TIKTOK_TOKEN_ENV = "STORYCLIPS_TIKTOK_TOKEN"  # noqa: S105  # nunca como argumento de línea de comandos


def _ledger(args: argparse.Namespace) -> Ledger:
    return Ledger(Path(args.ledger))


def _enqueue(args: argparse.Namespace) -> None:
    ledger = _ledger(args)
    video = Path(args.video)
    if not video.exists():
        raise FileNotFoundError(f"no existe {video}")
    title, description, tags = build_metadata(
        load_sidecar(video), args.tags.split(",") if args.tags else None
    )
    when = {"youtube": args.youtube_at, "tiktok": args.tiktok_at}
    if not any(when.values()):
        raise ValueError("indica --youtube-at y/o --tiktok-at (AAAA-MM-DDTHH:MM, hora de --tz)")
    for platform, text in when.items():
        if text:
            entry = ledger.enqueue(
                video=video, platform=platform, title=title, description=description, tags=tags,
                publish_at=parse_local(text, args.tz),
            )  # fmt: skip
            print(f"encolado en {platform}: {video.name} -> {entry.publish_at}")
    ledger.save()


def _slots(args: argparse.Namespace) -> None:
    hours = [time.fromisoformat(h) for h in args.times.split(",")]
    taken = [e.when() for e in _ledger(args).entries()]
    for slot in next_slots(datetime.now(UTC), hours, args.count, tz=args.tz, taken=taken):
        print(slot.isoformat(timespec="minutes"))


def _status(args: argparse.Namespace) -> None:
    entries = _ledger(args).entries()
    if not entries:
        print("la cola está vacía")
    for e in entries:
        extra = f"  id={e.remote_id}" if e.remote_id else ""
        extra += f"  ERROR: {e.error}" if e.error else ""
        print(f"{e.platform:<8}{e.status:<10}{e.publish_at}  {Path(e.video).name}{extra}")


def _run(args: argparse.Namespace) -> None:
    ledger = _ledger(args)

    def youtube() -> YouTubeClient:
        return GoogleYouTubeClient(Path(args.youtube_token))

    def tiktok() -> TikTokClient:
        token = os.environ.get(TIKTOK_TOKEN_ENV)
        if not token:
            raise YouTubeAuthError(
                f"define la variable de entorno {TIKTOK_TOKEN_ENV} con tu token de TikTok"
            )
        return HttpTikTokClient(token)

    report = run(
        ledger,
        datetime.now(UTC),
        youtube=youtube,
        tiktok=tiktok,
        live=args.live,
        config=PublishConfig(language=args.language, tiktok_privacy=args.tiktok_privacy),
    )
    mode = "EN VIVO" if args.live else "SIMULACIÓN (añade --live para publicar de verdad)"
    print(f"[{mode}]")
    for a in report.actions:
        print(f"  {a.entry.platform:<8}{a.kind:<7}{Path(a.entry.video).name}: {a.detail}")
    if not report.actions:
        print("  nada pendiente")


def _auth(args: argparse.Namespace) -> None:
    authorize(Path(args.client_secret), Path(args.youtube_token))
    print(f"token guardado en {args.youtube_token} (no lo subas a ningún repo)")


def add_parser(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    publish = sub.add_parser(
        "publish", help="cola de publicación en YouTube y TikTok"
    ).add_subparsers(dest="publish_command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--ledger", default="out/publish_queue.json")

    e = publish.add_parser("enqueue", help="programa un video (necesita su .json junto al mp4)")
    common(e)
    e.add_argument("video")
    e.add_argument("--youtube-at", help="AAAA-MM-DDTHH:MM en la hora de --tz")
    e.add_argument("--tiktok-at")
    e.add_argument("--tz", default=DEFAULT_TZ)
    e.add_argument("--tags", help="etiquetas extra separadas por coma")
    e.set_defaults(func=_enqueue)

    s = publish.add_parser("slots", help="próximos horarios libres a esas horas diarias")
    common(s)
    s.add_argument("--times", default="18:00,21:00", help="horas del día, p. ej. 12:00,18:00,21:00")
    s.add_argument("--count", type=int, default=5)
    s.add_argument("--tz", default=DEFAULT_TZ)
    s.set_defaults(func=_slots)

    r = publish.add_parser("run", help="procesa la cola (simulación salvo --live)")
    common(r)
    r.add_argument("--live", action="store_true", help="publica DE VERDAD (usa tus credenciales)")
    r.add_argument("--youtube-token", default=str(HOME / "youtube_token.json"))
    r.add_argument("--language", default="es")
    r.add_argument(
        "--tiktok-privacy", default="SELF_ONLY", help="SELF_ONLY hasta que TikTok audite tu app"
    )
    r.set_defaults(func=_run)

    st = publish.add_parser("status", help="estado de la cola")
    common(st)
    st.set_defaults(func=_status)

    a = publish.add_parser("auth-youtube", help="autoriza YouTube una vez (abre el navegador)")
    a.add_argument(
        "--client-secret", required=True, help="JSON de credenciales OAuth de escritorio"
    )
    a.add_argument("--youtube-token", default=str(HOME / "youtube_token.json"))
    a.set_defaults(func=_auth)
