"""Frases y cortes: dónde se parte una historia para que haya que ver la siguiente parte."""

from __future__ import annotations

import re

CUT_MARKER = "[CORTE]"
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
_URL = re.compile(r"https?://|www\.", re.IGNORECASE)
# Palabras que suelen anunciar un giro; sube la puntuación de la frase como punto de corte.
_HOOK_WORDS = (
    "entonces", "de repente", "pero", "nunca", "jamás", "lo que vi", "abrí", "then", "suddenly",
    "but", "never", "what i saw", "i opened", "that's when",
)  # fmt: skip


def split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for block in text.splitlines():
        for piece in _SENTENCE_END.split(block.strip()):
            piece = piece.strip()
            if piece:
                sentences.append(piece)
    return sentences


def has_url(text: str) -> bool:
    return bool(_URL.search(text))


def auto_cut(sentences: list[str], *, target: float = 0.6) -> int:
    """Índice donde empieza la parte 2: cerca del `target` del texto y en una frase de gancho.

    La parte 1 termina en la frase anterior al índice devuelto. Prefiere frases que acaban en `!`
    o `?`, o que anuncian un giro, dentro del tramo central de la historia.
    """
    n = len(sentences)
    if n < 2:
        raise ValueError("hacen falta al menos 2 frases para cortar una historia")
    total = sum(len(s) for s in sentences)
    best, best_score, seen = 1, float("-inf"), 0
    for i in range(1, n):
        seen += len(sentences[i - 1])  # caracteres de la parte 1 si se corta antes de i
        position = seen / total
        last = sentences[i - 1]
        score = -abs(position - target)
        if last.endswith(("!", "?")):
            score += 0.15
        if any(w in last.lower() for w in _HOOK_WORDS):
            score += 0.1
        if not 0.3 <= position <= 0.85:
            score -= 1.0  # un corte muy al principio o al final no engancha
        if score > best_score:
            best, best_score = i, score
    return best


def split_parts(text: str, *, parts: int = 2) -> list[list[str]]:
    """Frases de cada parte. Respeta los `[CORTE]` del texto; si no hay, corta con `auto_cut`."""
    chunks = [c for c in (p.strip() for p in text.split(CUT_MARKER)) if c]
    groups = [split_sentences(c) for c in chunks]
    groups = [g for g in groups if g]
    if len(groups) >= 2:
        return groups[: max(2, parts)] if parts >= 2 else groups
    sentences = groups[0] if groups else []
    if len(sentences) < 2:
        raise ValueError("la historia es demasiado corta para cortarla en partes")
    cut = auto_cut(sentences)
    return [sentences[:cut], sentences[cut:]]
