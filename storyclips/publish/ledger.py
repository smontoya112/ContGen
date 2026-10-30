"""Cola de publicaciones en un JSON: qué video va a qué plataforma y cuándo, y en qué paso va.

Es la memoria que evita subir dos veces el mismo video (idempotencia) y permite reanudar tras una caída.
El archivo se reescribe de forma atómica. Las credenciales NUNCA se guardan aquí.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

PLATFORMS = ("youtube", "tiktok")
STATUSES = ("queued", "uploaded", "published", "failed")


class LedgerError(Exception):
    """Entrada inválida o duplicada."""


@dataclass
class Entry:
    video: str  # ruta absoluta del mp4
    platform: str
    title: str
    description: str
    tags: list[str]
    publish_at: str  # ISO 8601 en UTC
    status: str = "queued"
    remote_id: str | None = None
    error: str | None = None
    attempts: int = 0
    history: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.platform}:{self.video}"

    def when(self) -> datetime:
        return datetime.fromisoformat(self.publish_at)


class Ledger:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._entries: dict[str, Entry] = {}
        if path.exists():
            for raw in json.loads(path.read_text(encoding="utf-8")):
                entry = Entry(**raw)
                self._entries[entry.key] = entry

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(
                [asdict(e) for e in self._entries.values()], out, ensure_ascii=False, indent=2
            )
        os.replace(tmp, self._path)

    def enqueue(
        self,
        *,
        video: Path,
        platform: str,
        title: str,
        description: str,
        tags: list[str],
        publish_at: datetime,
    ) -> Entry:
        if platform not in PLATFORMS:
            raise LedgerError(f"plataforma desconocida: {platform!r} (usa {PLATFORMS})")
        if publish_at.tzinfo is None:
            raise LedgerError("publish_at debe llevar zona horaria")
        entry = Entry(
            video=str(video.resolve()),
            platform=platform,
            title=title,
            description=description,
            tags=tags,
            publish_at=publish_at.astimezone(UTC).isoformat(),
        )
        existing = self._entries.get(entry.key)
        if existing is not None:
            if existing.status in ("uploaded", "published"):
                raise LedgerError(
                    f"{video.name} ya está en {platform} ({existing.status}): no se vuelve a encolar"
                )
            existing.publish_at = entry.publish_at  # reprogramar lo que sigue pendiente o falló
            existing.status, existing.error = "queued", None
            return existing
        self._entries[entry.key] = entry
        return entry

    def entries(self, platform: str | None = None) -> list[Entry]:
        return [e for e in self._entries.values() if platform in (None, e.platform)]

    def pending(self, now: datetime) -> list[Entry]:
        """Entradas por procesar, de la más próxima a la más lejana (las que fallaron se reintentan)."""
        todo = [e for e in self._entries.values() if e.status in ("queued", "failed")]
        return sorted(todo, key=lambda e: e.when())

    def refresh(self, entry: Entry, *, title: str, description: str, tags: list[str]) -> bool:
        """Actualiza el texto de una entrada que aún no se subió; devuelve si cambió algo."""
        if entry.status not in ("queued", "failed"):
            return False
        changed = (entry.title, entry.description, entry.tags) != (title, description, tags)
        entry.title, entry.description, entry.tags = title, description, tags
        return changed

    def record(
        self, entry: Entry, status: str, *, remote_id: str | None = None, error: str | None = None
    ) -> None:
        entry.status = status
        entry.remote_id = remote_id or entry.remote_id
        entry.error = error
        entry.attempts += 1
        entry.history.append(f"{datetime.now(UTC).isoformat(timespec='seconds')} {status}")
