"""Título, descripción y etiquetas de publicación a partir del archivo `.json` que deja el montaje."""

from __future__ import annotations

import json
import re
from pathlib import Path

DISCLOSURE = "Historia original de ficción, narrada con voz generada por IA."
# Etiquetas por defecto: formato y tema. Sin «historias reales» ni «true story»: son ficción y la descripción
# lo dice. Sin etiquetas de otra cosa (p. ej. un juego) que no aparezca en el video: sería engañoso.
DEFAULT_TAGS = ["shorts", "storytime", "historias", "trabajo", "confesiones", "ficcion"]
MAX_HASHTAGS = 8  # YouTube muestra los 3 primeros sobre el título; más de 15 se ignoran todos


_PART = re.compile(r"^(?P<slug>.+)_parte(?P<n>\d+)$")


def load_sidecar(video: Path) -> dict:
    """Datos del video: `<video>.json`, o, para `<slug>_parteN.mp4`, la parte N de `<slug>.json`."""
    own = video.with_suffix(".json")
    if own.exists():
        return json.loads(own.read_text(encoding="utf-8"))
    match = _PART.match(video.stem)
    story = video.with_name(f"{match['slug']}.json") if match else None
    if match and story is not None and story.exists():
        data = json.loads(story.read_text(encoding="utf-8"))
        part = next((p for p in data.get("parts", []) if p["index"] == int(match["n"])), None)
        if part is not None:
            return {
                **data,
                "title": part["title"],
                "hook": part.get("hook") or data.get("hook", ""),
                "part": part["index"],
                "n_parts": len(data["parts"]),
            }
    raise FileNotFoundError(
        f"falta {own.name} (o {video.stem.rsplit('_parte', 1)[0]}.json) junto al video"
    )


def _dedupe(items: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        clean = item.strip().lstrip("#").replace(" ", "").lower()
        if clean:
            seen.setdefault(clean, None)
    return list(seen)


def build_metadata(
    sidecar: dict, extra_tags: list[str] | None = None
) -> tuple[str, str, list[str]]:
    """(título, descripción, etiquetas). La descripción abre con el gancho, declara que es ficción con
    voz de IA y cierra con hashtags: primero los del tema de la historia y los de formato, que son los
    tres que YouTube muestra sobre el título."""
    title = str(sidecar["title"]).strip()[:100]
    story_tags = _dedupe(list(sidecar.get("tags") or []))
    extra = _dedupe(list(extra_tags or []))
    tags = _dedupe([*story_tags, *extra, *DEFAULT_TAGS])
    shown = _dedupe(
        [*story_tags[:1], "shorts", "storytime", *story_tags[1:], *extra, *DEFAULT_TAGS]
    )
    hashtags = " ".join(f"#{t}" for t in shown[:MAX_HASHTAGS])
    hook = str(sidecar.get("hook") or "").strip()
    more = ""
    if sidecar.get("part") and sidecar["part"] < sidecar.get("n_parts", 1):
        more = f"Continúa en la parte {sidecar['part'] + 1}."
    parts = [p for p in (hook, more, DISCLOSURE, hashtags) if p]
    return title, "\n\n".join(parts), tags
