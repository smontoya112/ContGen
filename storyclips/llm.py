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
    "Eres un narrador de confesiones tipo Reddit para video vertical. Escribes como una persona real "
    "que le cuenta a un amigo algo que le pasó: lenguaje SIMPLE y DIRECTO, frases cortas, palabras de "
    "todos los días, cero metáforas rebuscadas ni descripciones poéticas. Primera persona, ritmo rápido, "
    "detalles concretos (nombres, horas, lugares, cosas que se dijeron). Ficción ORIGINAL: nunca copies "
    "ni adaptes publicaciones reales, ni uses personas reales, marcas o datos personales. Nada de "
    "violencia explícita, muertes, armas, sangre, contenido sexual ni odio: el misterio y la tensión "
    "vienen de secretos, mentiras, descubrimientos y giros cotidianos."
)


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

    def complete(self, system: str, user: str, *, temperature: float = 0.7) -> str:
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


_OUTLINE = """Diseña el esquema de una confesión original tipo Reddit sobre: {topic}.
Idioma: {language}.
Escribe exactamente {beats} momentos numerados (1. a {beats}.), uno por línea, cada uno de una sola frase
que diga QUÉ pasa, con hechos concretos de la vida diaria (un vecino, un compañero, un familiar, un
mensaje, un objeto, una mentira). Reglas: narrador en primera persona; el momento 1 es un gancho fuerte;
el momento {cut} es el de MÁXIMA tensión, justo antes de una revelación, y no se resuelve; del
{next_beat} en adelante se revela y se cierra con un último giro. Sin violencia ni muertes.
Primera línea exacta, antes de la lista: TITULO: <título corto y llamativo, máximo 80 caracteres>
Sin comentarios.{feedback}"""

_PARAGRAPH = """Historia: {title}. Idioma: {language}.
Esquema:
{outline}

Texto escrito hasta ahora:
{written}

Escribe SOLO el párrafo del momento {n}: «{beat}».
Entre {min_words} y {max_words} palabras, de 3 a 5 frases CORTAS. Lenguaje simple y directo, como si se
lo contaras a un amigo: nada de metáforas ni descripciones poéticas; di qué pasó, qué dijiste y qué
sentiste. Primera persona, continúa el texto anterior sin repetirlo. {ending}{feedback}"""

_TITLE = re.compile(r"^\s*t[ií]tulo\s*:\s*(.+)$", re.IGNORECASE)
_BEAT = re.compile(r"^\s*\d+\s*[.)\-:]\s*(.+)$")


def _clean(raw: str) -> str:
    text = _FENCE.sub("", raw.strip()).strip()
    return text.replace(CUT_MARKER, " ").strip()


_VIOLENT = re.compile(
    r"\b(mat[ae]r?|mat[óo]|asesin\w*|cad[áa]ver\w*|sangre|sangrient\w*|enterr\w*|apu[ñn]al\w*|"
    r"degoll\w*|cuchill\w*|pistola|disparo\w*|tortur\w*|violaci[óo]n|suicid\w*)\b",
    re.IGNORECASE,
)


def _check_paragraph(text: str, *, min_words: int, max_words: int) -> None:
    words = len(text.split())
    problems: list[str] = []
    if not min_words <= words <= max_words:
        problems.append(f"{words} palabras (se pedían {min_words}-{max_words})")
    if has_url(text):
        problems.append("contiene enlaces")
    if hit := _VIOLENT.search(text):
        problems.append(f"menciona violencia explícita ({hit.group(0)!r}): reescríbelo sin ella")
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
        paragraph_words: tuple[int, int] = (22, 90),
        attempts: int = 4,
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
