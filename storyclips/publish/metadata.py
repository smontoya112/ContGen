"""Título, descripción y etiquetas de publicación a partir del archivo `.json` que deja el montaje."""

from __future__ import annotations

import json
from pathlib import Path

DISCLOSURE = "Historia original de ficción, narrada con voz generada por IA."
DEFAULT_TAGS = ["minecraft", "historias", "confesiones", "misterio", "storytime"]


def load_sidecar(video: Path) -> dict:
    """`<video>.json` (mismo nombre, junto al mp4); falla con un mensaje claro si no existe."""
    path = video.with_suffix(".json")
    if not path.exists():
        raise FileNotFoundError(f"falta {path.name} junto al video (lo genera `storyclips render`)")
    return json.loads(path.read_text(encoding="utf-8"))


def build_metadata(
    sidecar: dict, extra_tags: list[str] | None = None
) -> tuple[str, str, list[str]]:
    """(título, descripción, etiquetas). La descripción abre con el gancho, declara que es ficción con
    voz de IA y añade los hashtags."""
    title = str(sidecar["title"]).strip()[:100]
    tags = list(dict.fromkeys([*(extra_tags or []), *DEFAULT_TAGS]))
    hook = str(sidecar.get("hook") or "").strip()
    hashtags = " ".join(f"#{t.replace(' ', '')}" for t in tags[:8])
    parts = [p for p in (hook, DISCLOSURE, hashtags) if p]
    return title, "\n\n".join(parts), tags
