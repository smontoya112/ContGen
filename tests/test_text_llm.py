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


def test_the_writer_returns_a_valid_story_and_sends_an_openai_request() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_reply())

    story = StoryWriter(_client(handler), min_words=100, max_words=500).write(
        "un vecino misterioso"
    )

    assert story.title == "Mi vecino" and CUT_MARKER in story.text
    body = json.loads(seen[0].content)
    assert seen[0].url.path == "/v1/chat/completions" and body["model"] == "qwen-test"
    assert "un vecino misterioso" in body["messages"][1]["content"]
    assert "nunca copies" in body["messages"][0]["content"].lower()  # historias originales


def test_a_bad_answer_is_retried_with_the_reason_as_feedback() -> None:
    prompts: list[str] = []
    answers = iter(
        [
            httpx.Response(200, json={"choices": [{"message": {"content": "no es json"}}]}),
            httpx.Response(200, json=_reply()),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        prompts.append(json.loads(request.content)["messages"][1]["content"])
        return next(answers)

    story = StoryWriter(_client(handler), min_words=100, max_words=500).write("tema")

    assert story.title == "Mi vecino" and len(prompts) == 2
    assert "falló" in prompts[1] and "JSON" in prompts[1]


def test_it_gives_up_after_the_allowed_attempts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_reply(story="Muy corta. Mucho."))

    with pytest.raises(StoryError, match="sin historia válida tras 3 intentos"):
        StoryWriter(_client(handler)).write("tema")


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
