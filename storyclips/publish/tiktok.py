"""TikTok Content Posting API (subida directa por archivo).

NO se ha ejecutado contra la API real: necesita una app de TikTok for Developers con el producto
«Content Posting API» y un token de usuario con el permiso `video.publish`. Hasta que TikTok audite tu app,
solo se pueden publicar videos con `privacy_level = SELF_ONLY` (privados). La API no tiene programación:
la hora la controla la cola (`storyclips publish run`). Verifica los campos en la documentación vigente.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import httpx

API = "https://open.tiktokapis.com"
CHUNK = 64 * 1024 * 1024  # los trozos intermedios; el último absorbe el resto (hasta 128 MB)
_DONE = "PUBLISH_COMPLETE"
_INBOX = "SEND_TO_USER_INBOX"  # el video quedó en la bandeja del usuario para que lo publique él
_FAILED = "FAILED"


class TikTokError(Exception):
    """TikTok rechazó la petición o falló el procesamiento."""


class TikTokClient(Protocol):
    def post_video(self, path: Path, *, title: str, privacy_level: str, is_aigc: bool) -> str:
        """Sube y publica el video; devuelve el `publish_id`."""
        ...


def plan_chunks(size: int, chunk_size: int = CHUNK) -> list[tuple[int, int]]:
    """Rangos (inicio, fin inclusive) de cada trozo: uno solo si cabe; si no, trozos de `chunk_size` y
    el último con el resto (TikTok pide que el último trozo pueda ser mayor)."""
    if size <= 0:
        raise ValueError("el archivo está vacío")
    if size <= chunk_size:
        return [(0, size - 1)]
    count = size // chunk_size
    ranges = [(i * chunk_size, (i + 1) * chunk_size - 1) for i in range(count - 1)]
    ranges.append(((count - 1) * chunk_size, size - 1))
    return ranges


def build_init_body(
    *, title: str, privacy_level: str, size: int, is_aigc: bool, chunks: list[tuple[int, int]]
) -> dict[str, Any]:
    chunk_size = chunks[0][1] - chunks[0][0] + 1 if len(chunks) > 1 else size
    return {
        "post_info": {
            "title": title[:2200],
            "privacy_level": privacy_level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "is_aigc": is_aigc,  # etiqueta de contenido generado por IA
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": chunk_size,
            "total_chunk_count": len(chunks),
        },
    }


class HttpTikTokClient:
    def __init__(
        self,
        access_token: str,
        *,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        poll_every_s: float = 5.0,
        max_polls: int = 120,
    ) -> None:
        self._http = http or httpx.Client(timeout=120.0)
        self._headers = {"Authorization": f"Bearer {access_token}"}
        self._sleep, self._poll_every, self._max_polls = sleep, poll_every_s, max_polls

    def _call(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        response = self._http.post(
            f"{API}{path}",
            json=body,
            headers={**self._headers, "Content-Type": "application/json; charset=UTF-8"},
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise TikTokError(f"respuesta no JSON de TikTok ({response.status_code})") from exc
        error = payload.get("error") or {}
        if response.status_code >= 400 or error.get("code", "ok") != "ok":
            raise TikTokError(
                f"{error.get('code', response.status_code)}: {error.get('message', '')}"
            )
        return payload.get("data", {})

    def query_creator_info(self) -> dict[str, Any]:
        """Opciones de privacidad permitidas para esta cuenta (conviene mirarlas antes de publicar)."""
        return self._call("/v2/post/publish/creator_info/query/", {})

    def post_video(self, path: Path, *, title: str, privacy_level: str, is_aigc: bool) -> str:
        size = path.stat().st_size
        chunks = plan_chunks(size)
        data = self._call(
            "/v2/post/publish/video/init/",
            build_init_body(
                title=title, privacy_level=privacy_level, size=size, is_aigc=is_aigc, chunks=chunks
            ),
        )
        publish_id, upload_url = data["publish_id"], data["upload_url"]
        with path.open("rb") as video:
            for start, end in chunks:
                video.seek(start)
                part = video.read(end - start + 1)
                response = self._http.put(
                    upload_url,
                    content=part,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Range": f"bytes {start}-{end}/{size}",
                        "Content-Length": str(len(part)),
                    },
                )
                if response.status_code not in (200, 201, 206):
                    raise TikTokError(
                        f"falló la subida del trozo {start}-{end}: HTTP {response.status_code}"
                    )
        return self._wait(publish_id)

    def _wait(self, publish_id: str) -> str:
        for _ in range(self._max_polls):
            data = self._call("/v2/post/publish/status/fetch/", {"publish_id": publish_id})
            status = data.get("status", "")
            if status in (_DONE, _INBOX):
                return publish_id
            if status == _FAILED:
                raise TikTokError(
                    f"TikTok no pudo procesar el video: {data.get('fail_reason', 'sin motivo')}"
                )
            self._sleep(self._poll_every)
        raise TikTokError("TikTok tardó demasiado en procesar el video")
