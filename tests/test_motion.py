from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from storyclips.background import NoBackground, Source, pick_segment, scan_sources
from storyclips.ffmpeg import (
    active_intervals,
    analyze_activity,
    clip_command,
    freezedetect_command,
    parse_freezes,
    render_command,
)
from storyclips.models import Story
from storyclips.pipeline import produce
from storyclips.text import CUT_MARKER, split_parts
from storyclips.tts import FakeTTS

SAMPLE = """\
[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 10.5
[freezedetect @ 0x1] lavfi.freezedetect.freeze_duration: 50
[freezedetect @ 0x1] lavfi.freezedetect.freeze_end: 60.5
[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 100
"""


def _story(n: int = 30) -> Story:
    lines = [f"Esta es la frase número {i} de la historia entera." for i in range(n)]
    lines.insert(18, CUT_MARKER)
    return Story("Mi vecino y el sótano", "\n".join(lines))


# ------------------------------------------------------------------ movimiento


def test_freezes_are_parsed_and_an_open_one_lasts_until_the_end() -> None:
    assert parse_freezes(SAMPLE, 120.0) == [(10.5, 60.5), (100.0, 120.0)]


def test_active_intervals_are_what_is_left_after_removing_freezes() -> None:
    freezes = parse_freezes(SAMPLE, 120.0)
    assert active_intervals(120.0, freezes) == [(0.0, 10.5), (60.5, 100.0)]
    assert active_intervals(120.0, freezes, min_len=45.0) == []  # nada dura tanto


def test_a_video_that_is_frozen_after_ten_seconds_has_ten_seconds_of_motion() -> None:
    """El caso real: un menú de pausa de 12 minutos tras 10 s de movimiento."""
    freezes = [(9.9, 738.7)]
    assert active_intervals(738.7, freezes) == [(0.0, 9.9)]


def test_freezedetect_command_downscales_and_discards_audio() -> None:
    cmd = freezedetect_command(Path("v.mp4"))
    text = " ".join(cmd)
    assert "freezedetect=n=-50.0dB:d=1.0" in text and "scale=320" in text and "-an" in cmd


def test_activity_is_cached_next_to_the_video(tmp_path: Path) -> None:
    video = tmp_path / "juego.mp4"
    video.write_bytes(b"x" * 10)
    calls: list[list[str]] = []

    def fake(cmd: list[str]) -> str:
        calls.append(cmd)
        return SAMPLE

    first = analyze_activity(video, 120.0, run_ffmpeg_stderr=fake)
    second = analyze_activity(video, 120.0, run_ffmpeg_stderr=fake)

    assert first == second == [(0.0, 10.5), (60.5, 100.0)] and len(calls) == 1
    assert (tmp_path / "juego.mp4.activity.json").exists()
    video.write_bytes(b"y" * 11)  # el archivo cambió: se vuelve a analizar
    analyze_activity(video, 120.0, run_ffmpeg_stderr=fake)
    assert len(calls) == 2
    assert json.loads((tmp_path / "juego.mp4.activity.json").read_text())["intervals"]


# ------------------------------------------------------------------ elegir tramos


def test_segments_are_only_taken_from_moving_intervals() -> None:
    source = Source(Path("mc.mp4"), 700, ((0.0, 50.0), (300.0, 420.0)))
    rng = random.Random(1)
    for _ in range(100):
        seg = pick_segment([source], 40, rng)
        assert (0 <= seg.start <= 10) or (300 <= seg.start <= 380)
        assert not seg.loop


def test_a_mostly_frozen_video_is_refused_with_a_clear_reason() -> None:
    source = Source(Path("mc.mp4"), 738, ((0.0, 9.9),))
    with pytest.raises(NoBackground) as exc:
        pick_segment([source], 190, random.Random(0))
    text = str(exc.value)
    assert (
        "190 s seguidos con movimiento" in text and "dura 10 s" in text and "--allow-loop" in text
    )


def test_allow_loop_repeats_the_longest_moving_clip() -> None:
    source = Source(Path("mc.mp4"), 738, ((0.0, 9.9), (200.0, 204.0)))
    seg = pick_segment([source], 190, random.Random(0), allow_loop=True)
    assert seg.loop and seg.start == 0.0 and seg.clip_s == 9.9 and seg.duration_s == 190


def test_a_clip_too_short_is_not_worth_looping() -> None:
    with pytest.raises(NoBackground):
        pick_segment(
            [Source(Path("a.mp4"), 100, ((0.0, 2.0),))], 60, random.Random(0), allow_loop=True
        )


def test_scan_sources_uses_the_activity_analysis(tmp_path: Path) -> None:
    (tmp_path / "a.mp4").write_bytes(b"x")
    sources = scan_sources(tmp_path, lambda p: 100.0, analyze=lambda p, d: [(0.0, 12.0)])
    assert sources[0].active == ((0.0, 12.0),)


# ------------------------------------------------------------------ comandos


def test_render_command_can_loop_a_short_clip() -> None:
    cmd = render_command(Path("clip.mp4"), 0, 190, Path("v.wav"), "a.ass", Path("o.mp4"), loop=True)
    assert cmd[cmd.index("-stream_loop") : cmd.index("-stream_loop") + 2] == ["-stream_loop", "-1"]
    assert cmd.index("-stream_loop") < cmd.index("-i")
    assert "-stream_loop" not in render_command(
        Path("c.mp4"), 0, 5, Path("v.wav"), "a.ass", Path("o.mp4")
    )


def test_clip_command_recodes_without_audio() -> None:
    cmd = clip_command(Path("bg.mp4"), 1.5, 9.9, Path("clip.mp4"))
    assert "-an" in cmd and "libx264" in cmd and cmd[cmd.index("-t") + 1] == "9.900"


# ------------------------------------------------------------------ un solo video


def test_one_part_joins_the_whole_story_without_a_cut() -> None:
    (only,) = split_parts(_story().text, parts=1)
    assert len(only) == 30


def test_produce_one_video_has_no_part_cards(tmp_path: Path) -> None:
    commands: list[list[str]] = []
    results = produce(
        _story(),
        tts=FakeTTS(),
        sources=[Source(Path("mc.mp4"), 3600)],
        out_dir=tmp_path,
        run=lambda cmd, cwd: commands.append(cmd),
        rng=random.Random(0),
        parts=1,
    )
    (only,) = results
    assert only.total == 1 and only.video.name.endswith(".mp4") and "_parte" not in only.video.name
    assert only.title == "Mi vecino y el sótano"  # sin sufijo «(Parte 1/2)»
    ass = (tmp_path / "work").rglob("parte1.ass").__next__().read_text(encoding="utf-8")
    assert (
        "PARTE" not in ass
        and "siguiente video" not in ass
        and "Card" not in ass.split("[Events]")[1]
    )
    assert len(commands) == 1


def test_produce_with_a_short_background_cuts_a_clip_and_loops_it(tmp_path: Path) -> None:
    commands: list[list[str]] = []
    produce(
        _story(),
        tts=FakeTTS(),
        sources=[Source(Path("mc.mp4"), 738, ((0.0, 9.9),))],
        out_dir=tmp_path,
        run=lambda cmd, cwd: commands.append(cmd),
        rng=random.Random(0),
        parts=1,
        allow_loop=True,
    )
    clip, render = commands
    assert "fondo1.mp4" in clip[-1] and clip[clip.index("-t") + 1] == "9.900"
    assert "-stream_loop" in render and any("fondo1.mp4" in part for part in render)


def test_produce_refuses_a_frozen_background_by_default(tmp_path: Path) -> None:
    with pytest.raises(NoBackground):
        produce(
            _story(), tts=FakeTTS(), sources=[Source(Path("mc.mp4"), 738, ((0.0, 9.9),))],
            out_dir=tmp_path, run=lambda c, w: None, rng=random.Random(0), parts=1,
        )  # fmt: skip
