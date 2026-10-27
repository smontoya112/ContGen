"""Procesa la cola: sube a YouTube (programado) y publica en TikTok cuando llega su hora.

Por defecto es una SIMULACIÓN: no llama a ninguna API. Solo con `live=True` (bandera `--live` en la CLI)
usa los clientes. Un fallo en una entrada no detiene a las demás y queda anotado para reintentar.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from storyclips.publish.ledger import Entry, Ledger
from storyclips.publish.tiktok import TikTokClient
from storyclips.publish.youtube import YouTubeClient, build_upload_body, check_future


@dataclass(frozen=True)
class Action:
    entry: Entry
    kind: str  # "upload" | "wait" | "skip"
    detail: str


@dataclass
class RunReport:
    actions: list[Action]

    def count(self, kind: str) -> int:
        return sum(a.kind == kind for a in self.actions)


@dataclass(frozen=True)
class PublishConfig:
    language: str = "es"
    tiktok_privacy: str = "SELF_ONLY"  # solo privado hasta que TikTok audite tu app
    made_for_kids: bool = False
    synthetic_media: bool = True  # voz y guion generados por IA: se declara


def plan(ledger: Ledger, now: datetime, max_uploads: int | None = None) -> list[Action]:
    """Qué haría ahora: YouTube se sube ya (queda programado en la plataforma); TikTok espera su hora."""
    actions = []
    youtube_left = max_uploads
    for entry in ledger.pending(now):
        if not Path(entry.video).exists():
            actions.append(Action(entry, "skip", "el archivo de video ya no existe"))
        elif entry.platform == "youtube":
            if youtube_left is not None and youtube_left <= 0:
                actions.append(
                    Action(entry, "wait", "se sube en otra ejecución (límite diario de cuota)")
                )
                continue
            youtube_left = None if youtube_left is None else youtube_left - 1
            actions.append(Action(entry, "upload", f"subir y programar para {entry.publish_at}"))
        elif entry.when() <= now:
            actions.append(Action(entry, "upload", "publicar ahora (ya es su hora)"))
        else:
            actions.append(Action(entry, "wait", f"espera hasta {entry.publish_at}"))
    return actions


def run(
    ledger: Ledger,
    now: datetime,
    *,
    youtube: Callable[[], YouTubeClient] | None = None,
    tiktok: Callable[[], TikTokClient] | None = None,
    live: bool = False,
    config: PublishConfig | None = None,
    max_uploads: int | None = None,
) -> RunReport:
    """Ejecuta (o simula) lo pendiente. Los clientes se crean solo si hace falta (perezosos)."""
    config = config or PublishConfig()
    actions = plan(ledger, now, max_uploads)
    if not live:
        return RunReport(actions)

    clients: dict[str, object] = {}
    for action in actions:
        entry = action.entry
        if action.kind != "upload":
            continue
        try:
            if entry.platform == "youtube":
                if youtube is None:
                    raise RuntimeError("no hay cliente de YouTube configurado")
                clients.setdefault("youtube", youtube())
                check_future(entry.when(), now)
                body = build_upload_body(
                    title=entry.title,
                    description=entry.description,
                    tags=entry.tags,
                    publish_at=entry.when(),
                    language=config.language,
                    made_for_kids=config.made_for_kids,
                    synthetic_media=config.synthetic_media,
                )
                remote = clients["youtube"].upload_video(body, Path(entry.video))  # type: ignore[attr-defined]
                ledger.record(entry, "uploaded", remote_id=remote)
            else:
                if tiktok is None:
                    raise RuntimeError("no hay cliente de TikTok configurado")
                clients.setdefault("tiktok", tiktok())
                remote = clients["tiktok"].post_video(  # type: ignore[attr-defined]
                    Path(entry.video),
                    title=entry.title,
                    privacy_level=config.tiktok_privacy,
                    is_aigc=config.synthetic_media,
                )
                ledger.record(entry, "published", remote_id=remote)
        except Exception as exc:  # una entrada mala no tumba las demás
            ledger.record(entry, "failed", error=f"{type(exc).__name__}: {exc}")
        finally:
            ledger.save()
    return RunReport(actions)
