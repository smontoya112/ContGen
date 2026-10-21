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
    "sin contenido sexual, sin odio."
)

_USER = """Escribe una historia original sobre: {topic}.
Idioma: {language}.
Longitud total: entre {min_words} y {max_words} palabras (unas 25 a 35 frases). Una historia con
menos de {min_words} palabras es INCORRECTA: desarrolla la trama con detalles, diálogos y escenas.
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


_PART1 = """Escribe la PARTE 1 de una historia original sobre: {topic}.
Idioma: {language}.
Primera línea exacta: TITULO: <título de máximo 80 caracteres>
Después, el texto: entre {min_words} y {max_words} palabras (unas 12 a 20 frases). Menos de
{min_words} palabras es INCORRECTO: desarrolla con detalles y escenas.
Reglas: primera persona, frases cortas, ritmo rápido, gancho en la primera frase.
La parte debe terminar en el momento MÁS tenso, justo antes de una revelación, con una frase de
suspenso. No resuelvas nada. Escribe solo el título y el texto, sin comentarios.{feedback}"""

_PART2 = """Esta es la PARTE 1 de una historia original:

{part1}

Escribe la PARTE 2: continúa exactamente donde termina la parte 1 y cierra la historia con la
revelación y un último giro. Mismo estilo y narrador. Entre {min_words} y {max_words} palabras
(unas 12 a 20 frases); menos de {min_words} palabras es INCORRECTO.
Escribe solo el texto de la parte 2, sin título ni comentarios.{feedback}"""

_TITLE = re.compile(r"^\s*t[ií]tulo\s*:\s*(.+)$", re.IGNORECASE)


def _clean(raw: str) -> str:
    text = _FENCE.sub("", raw.strip()).strip()
    return text.replace(CUT_MARKER, " ").strip()


def _check_part(text: str, *, min_words: int, max_words: int) -> None:
    words = len(text.split())
    problems: list[str] = []
    if not min_words <= words <= max_words:
        problems.append(f"{words} palabras (se pedían {min_words}-{max_words})")
    if has_url(text):
        problems.append("contiene enlaces")
    if len(split_sentences(text)) < 5:
        problems.append("tiene menos de 5 frases")
    if problems:
        raise StoryError("; ".join(problems))


class StoryWriter:
    """Escribe en DOS llamadas (parte 1 que acaba en el momento más tenso, y parte 2 que continúa).

    Un LLM pequeño cumple mejor dos tareas cortas que una larga, y el corte coincide con el de los
    videos. Cada llamada se valida y reintenta con los motivos como feedback.
    """

    def __init__(
        self,
        client: ChatClient,
        *,
        language: str = "español neutro",
        min_words: int = 110,
        max_words: int = 230,
        attempts: int = 3,
    ) -> None:
        self._client = client
        self._language = language
        self._min, self._max, self._attempts = min_words, max_words, attempts

    def _ask(self, template: str, **fields: str) -> str:
        feedback = ""
        last: StoryError | None = None
        for _ in range(self._attempts):
            prompt = template.format(
                language=self._language, min_words=self._min, max_words=self._max,
                feedback=feedback, **fields,
            )  # fmt: skip
            raw = self._client.complete(_SYSTEM, prompt)
            try:
                _check_part(_clean(_strip_title(raw)[1]), min_words=self._min, max_words=self._max)
                return raw
            except StoryError as exc:
                last = exc
                feedback = f"\nLa respuesta anterior falló: {exc}. Corrígelo."
        raise StoryError(f"sin texto válido tras {self._attempts} intentos: {last}")

    def write(self, topic: str) -> Story:
        raw1 = self._ask(_PART1, topic=topic)
        title, body1 = _strip_title(raw1)
        part1 = _clean(body1)
        if not title or len(title) > 100:
            title = topic[:80].capitalize()
        part2 = _clean(self._ask(_PART2, part1=part1))
        return Story(title=title, text=f"{part1}\n{CUT_MARKER}\n{part2}")


def _strip_title(raw: str) -> tuple[str, str]:
    """(título, cuerpo): el título es la línea `TITULO: …` si la hay."""
    lines = _FENCE.sub("", raw.strip()).strip().splitlines()
    for i, line in enumerate(lines):
        match = _TITLE.match(line)
        if match:
            return match.group(1).strip().strip('"*'), "\n".join(lines[:i] + lines[i + 1 :])
        if line.strip():
            break
    return "", "\n".join(lines)
