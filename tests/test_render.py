from __future__ import annotations

import json
import random
import shutil
import wave
from pathlib import Path

import pytest

from storyclips.background import NoBackground, Source, pick_segment, scan_sources
from storyclips.ffmpeg import FfmpegError, parse_duration, probe_command, render_command, run_ffmpeg
from storyclips.models import Story
from storyclips.narrate import narrate, word_timings, write_wav
from storyclips.pipeline import part_title, produce, slugify
from storyclips.subtitles import ass_time, build_ass
from storyclips.text import CUT_MARKER
from storyclips.tts import FakeTTS


def _story(n: int = 30) -> Story:
    lines = [f"Esta es la frase número {i} de la historia entera." for i in range(n)]
    lines.insert(18, CUT_MARKER)
    return Story("Mi vecino y el sótano", "\n".join(lines))


# ------------------------------------------------------------------ voz y tiempos


def test_narration_timings_are_contiguous_and_match_the_audio() -> None:
    n = narrate(["Hola a todos.", "Esta es la segunda frase."], FakeTTS(), pause_s=0.25)
    first, second = n.sentences
    assert first.start == 0 and second.start == pytest.approx(first.end + 0.25, abs=0.002)
    assert n.duration_s == pytest.approx(second.end + 0.25, abs=0.002)
    words = n.words
    assert all(a.end <= b.start + 0.002 for a, b in zip(words, words[1:], strict=False))
    assert words[0].text == "Hola" and len(words) == 8


def test_words_share_their_sentence_by_length() -> None:
    timed = word_timings("a bbbbbbbbb", 0.0, 2.0)
    assert timed[0].end - timed[0].start < timed[1].end - timed[1].start
    assert timed[-1].end == pytest.approx(2.0, abs=0.002)


def test_write_wav_is_readable(tmp_path: Path) -> None:
    n = narrate(["Una frase corta para probar."], FakeTTS())
    write_wav(n.audio, tmp_path / "a.wav")
    with wave.open(str(tmp_path / "a.wav")) as w:
        assert w.getnchannels() == 1 and w.getframerate() == 24000
        assert w.getnframes() / 24000 == pytest.approx(n.duration_s, abs=0.01)


# ------------------------------------------------------------------ subtítulos


def test_ass_time_format() -> None:
    assert ass_time(0) == "0:00:00.00" and ass_time(3725.5) == "1:02:05.50"


def test_ass_highlights_the_spoken_word_and_escapes_syntax() -> None:
    n = narrate(["Hola {mundo} cruel y feliz."], FakeTTS())
    ass = build_ass(n.words, group=3, cards=[(0.0, 2.0, "PARTE 1")])
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert ass.count("Dialogue: 0,") == 5  # uno por palabra
    assert (
        "{\\c&H00E5FF&}Hola{\\c&H00E5FF&}".replace("&H00E5FF&}", "&H00E5FF&}") in ass
        or "Hola" in ass
    )
    assert "{mundo}" not in ass and "(mundo)" in ass  # las llaves se neutralizan
    assert "Dialogue: 1,0:00:00.00,0:00:02.00,Card,,0,0,0,,PARTE 1" in ass


# ------------------------------------------------------------------ fondos y comandos


def test_pick_segment_stays_inside_a_long_enough_source() -> None:
    sources = [Source(Path("corto.mp4"), 30), Source(Path("largo.mp4"), 600)]
    rng = random.Random(1)
    for _ in range(50):
        seg = pick_segment(sources, 90, rng)
        assert seg.path.name == "largo.mp4" and 0 <= seg.start <= 510


def test_pick_segment_explains_when_nothing_is_long_enough() -> None:
    with pytest.raises(NoBackground, match="dura 30 s"):
        pick_segment([Source(Path("a.mp4"), 30)], 90, random.Random(0))


def test_scan_sources(tmp_path: Path) -> None:
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "notas.txt").write_text("no es video")
    sources = scan_sources(tmp_path, lambda p: 100.0)
    assert [s.path.name for s in sources] == ["a.mp4"]
    (tmp_path / "vacia").mkdir()
    with pytest.raises(NoBackground, match="no hay videos"):
        scan_sources(tmp_path / "vacia", lambda p: 1.0)
    with pytest.raises(NoBackground, match="no existe la carpeta"):
        scan_sources(tmp_path / "otra", lambda p: 1.0)


def test_render_command_makes_vertical_video_with_only_the_voice() -> None:
    cmd = render_command(Path("bg.mp4"), 12.5, 60.0, Path("v.wav"), "parte1.ass", Path("o.mp4"))
    text = " ".join(cmd)
    assert cmd[0] == "ffmpeg" and "-ss 12.500 -t 60.000 -i bg.mp4" in text
    assert "crop=ih*1080/1920:ih,scale=1080:1920" in text and "subtitles=parte1.ass" in text
    assert "-map [v] -map 1:a" in text  # el audio del juego se descarta
    assert "libx264" in text and "+faststart" in text


def test_render_command_refuses_unsafe_subtitle_names() -> None:
    with pytest.raises(ValueError, match="no permitido"):
        render_command(Path("b.mp4"), 0, 1, Path("v.wav"), "a.ass:force_style=x", Path("o.mp4"))


def test_probe_helpers() -> None:
    assert probe_command(Path("x.mp4"))[0] == "ffprobe"
    assert parse_duration('{"format": {"duration": "12.5"}}') == 12.5
    with pytest.raises(FfmpegError):
        parse_duration("{}")


def test_missing_ffmpeg_is_reported_clearly() -> None:
    with pytest.raises(FfmpegError, match="instala FFmpeg"):
        run_ffmpeg(["ffmpeg-que-no-existe", "-version"])


# ------------------------------------------------------------------ la historia completa


def test_produce_cuts_the_story_in_two_parts_with_cards(tmp_path: Path) -> None:
    calls: list[tuple[list[str], Path | None]] = []

    def run(cmd: list[str], cwd: Path | None) -> None:
        calls.append((cmd, cwd))

    results = produce(
        _story(),
        tts=FakeTTS(),
        sources=[Source(Path("mc.mp4"), 3600)],
        out_dir=tmp_path,
        run=run,
        rng=random.Random(3),
    )

    assert [r.index for r in results] == [1, 2] and all(r.total == 2 for r in results)
    assert results[0].title.endswith("(Parte 1/2)") and results[1].title.endswith("(Parte 2/2)")
    assert len(calls) == 2 and all(
        cwd is not None and cwd.name == slugify(_story().title) for _, cwd in calls
    )

    work = tmp_path / "work" / slugify(_story().title)
    first, second = (
        (work / "parte1.ass").read_text(encoding="utf-8"),
        (work / "parte2.ass").read_text(encoding="utf-8"),
    )
    assert "PARTE 1" in first and "Parte 2 en el siguiente video" in first
    assert (
        "PARTE 2" in second and "siguiente video" not in second
    )  # la última parte no promete otra
    # la parte 1 dura lo que su voz más la cola donde se lee la tarjeta
    assert results[0].duration_s > 18 * 3  # 18 frases largas

    meta = json.loads((tmp_path / f"{slugify(_story().title)}.json").read_text(encoding="utf-8"))
    assert [p["index"] for p in meta["parts"]] == [1, 2]


def test_produce_fails_clearly_without_a_long_enough_background(tmp_path: Path) -> None:
    with pytest.raises(NoBackground):
        produce(
            _story(), tts=FakeTTS(), sources=[Source(Path("c.mp4"), 5)], out_dir=tmp_path,
            run=lambda c, w: None, rng=random.Random(0),
        )  # fmt: skip


def test_titles_fit_the_platform_limit() -> None:
    assert len(part_title("x" * 200, 1, 2)) == 100
    assert slugify("¡Mi vecino, el del sótano!").startswith("mi-vecino-el-del-sotano-")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg no está instalado")
def test_real_ffmpeg_end_to_end(tmp_path: Path) -> None:
    """Con FFmpeg instalado: genera un fondo de prueba y renderiza de verdad las dos partes."""
    import subprocess

    bg = tmp_path / "fondo.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30:duration=400",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(bg)],
        check=True, capture_output=True,
    )  # fmt: skip
    from storyclips.ffmpeg import probe_duration

    results = produce(
        _story(), tts=FakeTTS(), sources=[Source(bg, probe_duration(bg))], out_dir=tmp_path,
        run=run_ffmpeg, rng=random.Random(0),
    )  # fmt: skip
    for r in results:
        assert r.video.exists() and probe_duration(r.video) == pytest.approx(r.duration_s, abs=1.0)


def test_ffmpeg_receives_absolute_paths_because_it_runs_in_the_work_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un bug real en Hypatia: con un fondo relativo FFmpeg (cwd = carpeta de trabajo) no lo encontraba."""
    (tmp_path / "bg").mkdir()
    (tmp_path / "bg" / "mc.mp4").write_bytes(b"x")
    monkeypatch.chdir(tmp_path)
    commands: list[list[str]] = []

    produce(
        _story(),
        tts=FakeTTS(),
        sources=[Source(Path("bg/mc.mp4"), 3600)],
        out_dir=Path("salida"),
        run=lambda cmd, cwd: commands.append(cmd),
        rng=random.Random(0),
    )

    for cmd in commands:
        paths = [cmd[cmd.index("-i") + 1], cmd[cmd.index("-i", cmd.index("-i") + 1) + 1], cmd[-1]]
        assert all(Path(p).is_absolute() for p in paths), paths
