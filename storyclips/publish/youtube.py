"""YouTube Data API v3: subida programada (`privacyStatus: private` + `publishAt`).

`GoogleYouTubeClient` es un adaptador delgado que NO se ha ejecutado contra la API real (necesita tus
credenciales OAuth: `storyclips publish auth-youtube`). Todo lo demás se prueba con un cliente falso.
Cada subida de video cuesta unas 1 600 unidades de la cuota diaria (10 000 por defecto): confírmalo en la
documentación vigente; los proyectos de API sin auditar solo pueden subir videos privados.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

MIN_LEAD = timedelta(minutes=15)  # publishAt debe quedar en el futuro


class YouTubeClient(Protocol):
    def upload_video(self, body: dict[str, Any], path: Path) -> str:
        """Sube el archivo con ese cuerpo y devuelve el id del video."""
        ...


class YouTubeAuthError(Exception):
    """Faltan credenciales o la librería de Google."""


def build_upload_body(
    *,
    title: str,
    description: str,
    tags: list[str],
    publish_at: datetime,
    language: str = "es",
    category_id: str = "24",  # Entertainment
    made_for_kids: bool = False,
    synthetic_media: bool = True,
) -> dict[str, Any]:
    """Cuerpo de `videos.insert`. Este contenido NO es para niños (`selfDeclaredMadeForKids` False, y
    hay que declararlo bien) y usa voz y guion generados por IA (`containsSyntheticMedia` True)."""
    if publish_at.tzinfo is None:
        raise ValueError("publish_at debe llevar zona horaria")
    if len(title) > 100:
        raise ValueError("el título de YouTube admite 100 caracteres como máximo")
    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
            "defaultLanguage": language,
            "defaultAudioLanguage": language,
        },
        "status": {
            "privacyStatus": "private",  # se hace público solo en publishAt
            "publishAt": publish_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "selfDeclaredMadeForKids": made_for_kids,
            "containsSyntheticMedia": synthetic_media,
        },
    }


def check_future(publish_at: datetime, now: datetime) -> None:
    if publish_at < now + MIN_LEAD:
        raise ValueError(
            f"publish_at {publish_at:%Y-%m-%d %H:%M} UTC debe quedar al menos {int(MIN_LEAD.total_seconds() // 60)} "
            "minutos en el futuro"
        )


class GoogleYouTubeClient:
    """Subida reanudable con google-api-python-client (`uv sync --extra youtube`)."""

    SCOPE = "https://www.googleapis.com/auth/youtube.upload"

    def __init__(self, token_file: Path) -> None:
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise YouTubeAuthError(
                "falta google-api-python-client: corre `uv sync --extra youtube`"
            ) from exc
        if not token_file.exists():
            raise YouTubeAuthError(
                f"falta {token_file}: corre `storyclips publish auth-youtube` una vez"
            )
        creds = Credentials.from_authorized_user_file(str(token_file), [self.SCOPE])
        self._service = build("youtube", "v3", credentials=creds, cache_discovery=False)

    def upload_video(self, body: dict[str, Any], path: Path) -> str:
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(
            str(path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True
        )
        request = self._service.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _, response = request.next_chunk()
        return str(response["id"])


def authorize(client_secret: Path, token_file: Path) -> None:
    """Flujo OAuth de escritorio: abre el navegador UNA vez y guarda el token (permisos 600)."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise YouTubeAuthError(
            "falta google-auth-oauthlib: corre `uv sync --extra youtube`"
        ) from exc
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secret), [GoogleYouTubeClient.SCOPE]
    )
    creds = flow.run_local_server(port=0)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    token_file.chmod(0o600)


def now_utc() -> datetime:
    return datetime.now(UTC)
