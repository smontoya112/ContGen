from __future__ import annotations

import json

import httpx
import pytest

from storyclips.llm import ChatClient, LlmConfig, StoryError, StoryWriter, parse_story
from storyclips.text import CUT_MARKER, auto_cut, split_parts, split_sentences


def _sentences(n: int) -> list[str]:
    return [f"Esta es la frase número {i} de la historia." for i in range(n)]


def _story_text(n: int = 40, cut_at: int | None = 24) -> str:
    s = _sentences(n)
    if cut_at is not None:
        s.insert(cut_at, CUT_MARKER)
    return "\n".join(s)


# ------------------------------------------------------------------ cortes


def test_split_sentences_handles_newlines_and_punctuation() -> None:
    assert split_sentences("Hola. ¿Qué tal? Bien!\nOtra línea sin punto") == [
        "Hola.", "¿Qué tal?", "Bien!", "Otra línea sin punto",
    ]  # fmt: skip


def test_the_marker_decides_where_to_cut() -> None:
    parts = split_parts(_story_text(40, cut_at=24))
    assert [len(p) for p in parts] == [24, 16]


def test_without_a_marker_it_cuts_near_the_middle_on_a_hook() -> None:
    sentences = _sentences(30)
    sentences[17] = "Entonces abrí la puerta y no podía creer lo que vi!"
    cut = auto_cut(sentences)
    assert cut == 18  # la parte 1 acaba en la frase de gancho (índice 17)
    parts = split_parts("\n".join(sentences))
    assert len(parts) == 2 and parts[0][-1].endswith("vi!")


def test_the_automatic_cut_never_lands_at_the_very_start_or_end() -> None:
    cut = auto_cut(_sentences(10))
    assert 3 <= cut <= 8


def test_too_short_stories_are_refused() -> None:
    with pytest.raises(ValueError, match="demasiado corta"):
        split_parts("Una sola frase.")


# ------------------------------------------------------------------ LLM


def _reply(title: str = "Mi vecino", story: str | None = None) -> dict:
    return {
        "choices": [
            {"message": {"content": json.dumps({"title": title, "story": story or _story_text()})}}
        ]
    }


def _client(handler) -> ChatClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return ChatClient(LlmConfig(base_url="http://llm.test/v1", model="qwen-test"), http)


def _paragraph(tag: str, n: int = 40) -> str:
    return " ".join(f"palabra{tag}{i}" for i in range(n)) + "."


def _outline(beats: int = 8, title: str | None = "El vecino del sótano") -> str:
    lines = [f"TITULO: {title}"] if title else []
    return "\n".join(lines + [f"{i}. Pasa algo número {i}" for i in range(1, beats + 1)])


def _chat(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def _writer(replies: list[str], prompts: list[str] | None = None, **kw) -> StoryWriter:
    answers = iter(replies)

    def handler(request: httpx.Request) -> httpx.Response:
        if prompts is not None:
            prompts.append(json.loads(request.content)["messages"][1]["content"])
        return _chat(next(answers))

    return StoryWriter(_client(handler), **kw)


def _story_replies() -> list[str]:
    return [_outline(), *[_paragraph(str(i)) for i in range(1, 9)]]


def test_the_writer_builds_the_story_from_an_outline_and_cuts_at_the_tense_moment() -> None:
    prompts: list[str] = []
    story = _writer(_story_replies(), prompts).write("un vecino misterioso")

    assert story.title == "El vecino del sótano"
    first, second = story.text.split(CUT_MARKER)
    assert "palabra11" in first and "palabra41" in first and "palabra51" not in first
    assert "palabra51" in second and "palabra81" in second
    assert len(prompts) == 9 and "un vecino misterioso" in prompts[0]
    assert "palabra11" in prompts[2]  # cada párrafo ve lo ya escrito
    assert (
        "SIN revelar" in prompts[4] and "SIN revelar" not in prompts[3]
    )  # el momento 4 acaba en suspenso
    assert "cierra la historia" in prompts[8]


def test_the_story_is_long_enough_for_a_minute_and_a_half_of_voice() -> None:
    story = _writer(_story_replies()).write("tema")
    assert len(story.text.replace(CUT_MARKER, " ").split()) >= 8 * 28


def test_a_wrong_outline_is_retried_with_the_reason() -> None:
    prompts: list[str] = []
    replies = [_outline(beats=5), *_story_replies()]
    story = _writer(replies, prompts).write("tema")
    assert story.title == "El vecino del sótano"
    assert "falló" in prompts[1] and "5 momentos" in prompts[1]


def test_a_short_paragraph_is_retried_with_the_reason() -> None:
    prompts: list[str] = []
    replies = [_outline(), _paragraph("x", 5), *[_paragraph(str(i)) for i in range(1, 9)]]
    _writer(replies, prompts).write("tema")
    assert "falló" in prompts[2] and "5 palabras" in prompts[2]


def test_a_missing_title_falls_back_to_the_topic() -> None:
    replies = [_outline(title=None), *[_paragraph(str(i)) for i in range(1, 9)]]
    assert _writer(replies).write("un vecino raro").title == "Un vecino raro"


def test_it_gives_up_after_the_allowed_attempts() -> None:
    replies = [_outline(), "corto", "corto", "corto", "corto"]
    with pytest.raises(StoryError, match="sin respuesta válida tras 4 intentos"):
        _writer(replies).write("tema")


def test_links_in_a_paragraph_are_refused() -> None:
    bad = _paragraph("l") + " Mira https://reddit.com/x"
    with pytest.raises(StoryError, match="enlaces"):
        _writer([_outline(), bad, bad, bad, bad]).write("tema")


def test_beats_must_be_even_and_at_least_four() -> None:
    for beats in (3, 5, 2):
        with pytest.raises(ValueError, match="par"):
            StoryWriter(_client(lambda r: _chat("")), beats=beats)


@pytest.mark.parametrize(
    ("story", "problem"),
    [
        ("Mira https://reddit.com/r/x. " + _story_text(), "enlaces"),
        ("Frase. Otra. Tres.", "palabras"),
    ],
)
def test_parse_story_rejects_links_and_wrong_lengths(story: str, problem: str) -> None:
    raw = json.dumps({"title": "T", "story": story})
    with pytest.raises(StoryError, match=problem):
        parse_story(raw, min_words=100, max_words=500)


def test_json_in_a_code_fence_is_accepted() -> None:
    raw = "```json\n" + json.dumps({"title": "T", "story": _story_text()}) + "\n```"
    assert parse_story(raw, min_words=100, max_words=500).title == "T"


def test_explicit_violence_is_refused_and_retried_with_the_reason() -> None:
    prompts: list[str] = []
    violent = _paragraph("v") + " Entonces enterré al vecino."
    replies = [_outline(), violent, *[_paragraph(str(i)) for i in range(1, 9)]]
    story = _writer(replies, prompts).write("tema")
    assert "violencia explícita" in prompts[2] and "enterr" in prompts[2]
    assert "enterré" not in story.text


@pytest.mark.parametrize("word", ["asesinato", "sangre", "mató", "cuchillo", "cadáver"])
def test_the_violence_filter_catches_common_words(word: str) -> None:
    bad = _paragraph("v") + f" Había {word} ahí."
    with pytest.raises(StoryError, match="violencia"):
        _writer([_outline(), bad, bad, bad, bad]).write("tema")


def test_the_prompts_ask_for_simple_direct_confession_style() -> None:
    prompts: list[str] = []
    _writer(_story_replies(), prompts).write("tema")
    assert "tipo Reddit" in prompts[0] and "Sin violencia" in prompts[0]
    assert "simple y directo" in prompts[1] and "CORTAS" in prompts[1]
