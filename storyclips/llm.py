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


_OUTLINE = """Diseña el esquema de una historia original sobre: {topic}.
Idioma: {language}.
Escribe exactamente {beats} momentos numerados (1. a {beats}.), uno por línea, cada uno de una sola frase
que diga QUÉ pasa. Reglas: narrador en primera persona; el momento 1 es un gancho fuerte; el momento
{cut} es el de MÁXIMA tensión, justo antes de una revelación, y no se resuelve; del {next_beat} en
adelante se revela y se cierra con un último giro.
Primera línea exacta, antes de la lista: TITULO: <título de máximo 80 caracteres>
Sin comentarios.{feedback}"""

_PARAGRAPH = """Historia: {title}. Idioma: {language}.
Esquema:
{outline}

Texto escrito hasta ahora:
{written}

Escribe SOLO el párrafo del momento {n}: «{beat}».
Entre {min_words} y {max_words} palabras (4 a 6 frases cortas), primera persona, con detalles y
sensaciones. Continúa el texto anterior sin repetirlo. {ending}{feedback}"""

_TITLE = re.compile(r"^\s*t[ií]tulo\s*:\s*(.+)$", re.IGNORECASE)
_BEAT = re.compile(r"^\s*\d+\s*[.)\-:]\s*(.+)$")


def _clean(raw: str) -> str:
    text = _FENCE.sub("", raw.strip()).strip()
    return text.replace(CUT_MARKER, " ").strip()


def _check_paragraph(text: str, *, min_words: int, max_words: int) -> None:
    words = len(text.split())
    problems: list[str] = []
    if not min_words <= words <= max_words:
        problems.append(f"{words} palabras (se pedían {min_words}-{max_words})")
    if has_url(text):
        problems.append("contiene enlaces")
    if problems:
        raise StoryError("; ".join(problems))


def parse_outline(raw: str, beats: int) -> tuple[str, list[str]]:
    """(título, momentos) de la respuesta del esquema; falla si no hay exactamente `beats` momentos."""
    title, items = "", []
    for line in _FENCE.sub("", raw.strip()).strip().splitlines():
        if (match := _TITLE.match(line)) and not title:
            title = match.group(1).strip().strip('"*')
        elif match := _BEAT.match(line):
            items.append(match.group(1).strip())
    if len(items) != beats:
        raise StoryError(f"el esquema tiene {len(items)} momentos (se pedían {beats})")
    return title, items


class StoryWriter:
    """Escribe por pasos: un esquema de `beats` momentos y un párrafo por momento.

    Un LLM pequeño no respeta la longitud pedida de un tirón (salían 23-90 palabras en vez de 220+),
    pero sí cumple tareas cortas: la longitud queda controlada por el número de párrafos. El momento
    de máxima tensión (`cut`) cierra la parte 1; la parte 2 continúa y resuelve.
    """

    def __init__(
        self,
        client: ChatClient,
        *,
        language: str = "español neutro",
        beats: int = 8,
        paragraph_words: tuple[int, int] = (28, 110),
        attempts: int = 3,
    ) -> None:
        if beats < 4 or beats % 2:
            raise ValueError("beats debe ser par y de al menos 4")
        self._client = client
        self._language = language
        self._beats = beats
        self._min, self._max = paragraph_words
        self._attempts = attempts

    def _retry(self, prompt_for, validate):
        feedback, last = "", None
        for _ in range(self._attempts):
            raw = self._client.complete(_SYSTEM, prompt_for(feedback))
            try:
                return validate(raw)
            except StoryError as exc:
                last = exc
                feedback = f"\nLa respuesta anterior falló: {exc}. Corrígelo."
        raise StoryError(f"sin respuesta válida tras {self._attempts} intentos: {last}")

    def write(self, topic: str) -> Story:
        cut = self._beats // 2
        title, beats = self._retry(
            lambda fb: _OUTLINE.format(
                topic=topic,
                language=self._language,
                beats=self._beats,
                cut=cut,
                next_beat=cut + 1,
                feedback=fb,
            ),  # fmt: skip
            lambda raw: parse_outline(raw, self._beats),
        )
        if not title or len(title) > 100:
            title = topic[:80].capitalize()
        outline = "\n".join(f"{i}. {b}" for i, b in enumerate(beats, start=1))

        paragraphs: list[str] = []
        for n, beat in enumerate(beats, start=1):
            ending = (
                "Termina con una frase de suspenso, SIN revelar lo que sigue. "
                if n == cut
                else "Si es el último momento, cierra la historia con un giro. "
                if n == self._beats
                else ""
            )
            written = "\n".join(paragraphs) or "(todavía nada: empieza la historia)"
            paragraph = self._retry(
                lambda fb, n=n, beat=beat, ending=ending, written=written: _PARAGRAPH.format(
                    title=title,
                    language=self._language,
                    outline=outline,
                    written=written,
                    n=n,
                    beat=beat,
                    min_words=self._min,
                    max_words=self._max,
                    ending=ending,
                    feedback=fb,
                ),  # fmt: skip
                lambda raw: self._valid_paragraph(raw),
            )
            paragraphs.append(paragraph)
        first, second = "\n".join(paragraphs[:cut]), "\n".join(paragraphs[cut:])
        return Story(title=title, text=f"{first}\n{CUT_MARKER}\n{second}")

    def _valid_paragraph(self, raw: str) -> str:
        text = _clean(raw)
        _check_paragraph(text, min_words=self._min, max_words=self._max)
        return text
