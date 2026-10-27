"""Título, descripción y etiquetas de publicación a partir del archivo `.json` que deja el montaje."""

from __future__ import annotations

import json
import re
from pathlib import Path

DISCLOSURE = "Historia original de ficción, narrada con voz generada por IA."
DEFAULT_TAGS = ["minecraft", "historias", "confesiones", "misterio", "storytime"]


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


def build_metadata(
    sidecar: dict, extra_tags: list[str] | None = None
) -> tuple[str, str, list[str]]:
    """(título, descripción, etiquetas). La descripción abre con el gancho, declara que es ficción con
    voz de IA y añade los hashtags."""
    title = str(sidecar["title"]).strip()[:100]
    tags = list(dict.fromkeys([*(extra_tags or []), *DEFAULT_TAGS]))
    hook = str(sidecar.get("hook") or "").strip()
    hashtags = " ".join(f"#{t.replace(' ', '')}" for t in tags[:8])
    more = ""
    if sidecar.get("part") and sidecar["part"] < sidecar.get("n_parts", 1):
        more = f"Continúa en la parte {sidecar['part'] + 1}."
    parts = [p for p in (hook, more, DISCLOSURE, hashtags) if p]
    return title, "\n\n".join(parts), tags
