"""Escritor de historias con cualquier LLM compatible con OpenAI (Qwen por API, Ollama, vLLM…).

Las historias son ORIGINALES: el prompt prohíbe copiar publicaciones reales y no se descarga nada de
Reddit ni de otra web. Una respuesta mala (JSON roto, muy corta, con enlaces) se reintenta con los
motivos como feedback.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import httpx

from storyclips.models import Story
from storyclips.text import CUT_MARKER, has_url, split_sentences

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)

_SYSTEM = (
    "Eres guionista de historias cortas para video vertical narradas en primera persona, con "
    "ganchos fuertes. Escribes ficción ORIGINAL: nunca copies ni adaptes publicaciones reales de "
    "Reddit u otras webs, ni uses personas reales, marcas o datos personales. Sin violencia gráfica, "
    "sin contenido sexual, sin odio. Respondes SOLO con JSON."
)

_USER = """Escribe una historia original sobre: {topic}.
Idioma: {language}.
Longitud total: entre {min_words} y {max_words} palabras.
Reglas:
- Primera persona, frases cortas, ritmo rápido, un gancho en la primera frase.
- Coloca la marca {marker} en una línea sola en el momento MÁS tenso de la historia (un giro o un
  descubrimiento), a más o menos el 55-65 % del texto. Quien vea la parte 1 debe quedarse con ganas
  de ver la parte 2. La historia continúa y termina después de la marca.
- Termina con un cierre que dé gusto (o un último giro).
Devuelve JSON: {{"title": "título de máximo 80 caracteres", "story": "texto con la marca"}}
{feedback}"""


class StoryError(Exception):
    """El LLM no entregó una historia válida."""


@dataclass(frozen=True)
class LlmConfig:
    base_url: str = "http://localhost:11434/v1"  # Ollama por defecto
    model: str = "qwen2.5:7b"
    api_key: str | None = None
    timeout_s: float = 120.0

    @classmethod
    def from_env(cls) -> LlmConfig:
        env = os.environ
        return cls(
            base_url=env.get("STORYCLIPS_LLM_BASE_URL", cls.base_url),
            model=env.get("STORYCLIPS_LLM_MODEL", cls.model),
            api_key=env.get("STORYCLIPS_LLM_API_KEY"),
        )


class ChatClient:
    def __init__(self, config: LlmConfig, http: httpx.Client | None = None) -> None:
        headers = {"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}
        self._http = http or httpx.Client(timeout=config.timeout_s, headers=headers)
        self._config = config

    def complete(self, system: str, user: str, *, temperature: float = 0.9) -> str:
        response = self._http.post(
            f"{self._config.base_url.rstrip('/')}/chat/completions",
            json={
                "model": self._config.model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        response.raise_for_status()
        try:
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise StoryError(f"respuesta inesperada del LLM: {response.text[:200]}") from exc


def parse_story(raw: str, *, min_words: int, max_words: int) -> Story:
    """Valida la respuesta del LLM; lanza `StoryError` con el motivo."""
    try:
        data = json.loads(_FENCE.sub("", raw.strip()))
        title, text = str(data["title"]).strip(), str(data["story"]).strip()
    except (ValueError, KeyError, TypeError) as exc:
        raise StoryError("la respuesta no es un JSON con 'title' y 'story'") from exc

    words = len(text.replace(CUT_MARKER, " ").split())
    problems: list[str] = []
    if not title or len(title) > 100:
        problems.append("el título está vacío o pasa de 100 caracteres")
    if not min_words <= words <= max_words:
        problems.append(f"{words} palabras (se pedían {min_words}-{max_words})")
    if has_url(text) or has_url(title):
        problems.append("contiene enlaces")
    if len(split_sentences(text.replace(CUT_MARKER, "\n"))) < 6:
        problems.append("tiene menos de 6 frases")
    if problems:
        raise StoryError("; ".join(problems))
    return Story(title=title, text=text)


class StoryWriter:
    def __init__(
        self,
        client: ChatClient,
        *,
        language: str = "español neutro",
        min_words: int = 220,
        max_words: int = 420,
        attempts: int = 3,
    ) -> None:
        self._client = client
        self._language = language
        self._min, self._max, self._attempts = min_words, max_words, attempts

    def write(self, topic: str) -> Story:
        feedback = ""
        last: StoryError | None = None
        for _ in range(self._attempts):
            prompt = _USER.format(
                topic=topic, language=self._language, min_words=self._min, max_words=self._max,
                marker=CUT_MARKER, feedback=feedback,
            )  # fmt: skip
            try:
                return parse_story(
                    self._client.complete(_SYSTEM, prompt), min_words=self._min, max_words=self._max
                )
            except StoryError as exc:
                last = exc
                feedback = f"\nLa respuesta anterior falló: {exc}. Corrígelo."
        raise StoryError(f"sin historia válida tras {self._attempts} intentos: {last}")
