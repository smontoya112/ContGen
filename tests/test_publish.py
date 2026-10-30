from __future__ import annotations

import json
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from storyclips.cli import main
from storyclips.publish.ledger import Ledger, LedgerError
from storyclips.publish.metadata import DISCLOSURE, build_metadata, load_sidecar
from storyclips.publish.runner import PublishConfig, plan, run
from storyclips.publish.schedule import next_slots, parse_local
from storyclips.publish.tiktok import (
    CHUNK,
    HttpTikTokClient,
    TikTokError,
    build_init_body,
    plan_chunks,
)
from storyclips.publish.youtube import build_upload_body, check_future

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def _video(tmp_path: Path, name: str = "historia.mp4") -> Path:
    video = tmp_path / name
    video.write_bytes(b"0" * 1000)
    video.with_suffix(".json").write_text(
        json.dumps(
            {"title": "El vecino del sótano", "hook": "Siempre cerraba la puerta con llave."}
        ),
        encoding="utf-8",
    )
    return video


class FakeYouTube:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[dict[str, Any], Path]] = []
        self.fail = fail

    def upload_video(self, body: dict[str, Any], path: Path) -> str:
        if self.fail:
            raise ConnectionError("sin red")
        self.calls.append((body, path))
        return "yt123"


class FakeTikTok:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def post_video(self, path: Path, *, title: str, privacy_level: str, is_aigc: bool) -> str:
        self.calls.append({"path": path, "title": title, "privacy": privacy_level, "aigc": is_aigc})
        return "tt456"


# ------------------------------------------------------------------ horarios


def test_naive_times_are_local_to_the_timezone() -> None:
    assert parse_local("2026-11-02T18:30").utcoffset() == timedelta(hours=-5)  # Bogotá
    assert parse_local("2026-11-02T18:30Z").utcoffset() == timedelta(0)


def test_next_slots_skip_the_past_and_the_taken_ones() -> None:
    after = datetime(2026, 11, 2, 23, 30, tzinfo=UTC)  # 18:30 en Bogotá
    first = next_slots(after, [time(18), time(21)], 3)
    assert [s.strftime("%m-%d %H:%M") for s in first] == [
        "11-02 21:00",
        "11-03 18:00",
        "11-03 21:00",
    ]
    again = next_slots(after, [time(18), time(21)], 2, taken=[first[0]])
    assert again[0] == first[1]
    with pytest.raises(ValueError, match="al menos una hora"):
        next_slots(after, [], 1)


# ------------------------------------------------------------------ metadatos


def test_metadata_discloses_fiction_and_ai_voice(tmp_path: Path) -> None:
    title, description, tags = build_metadata(load_sidecar(_video(tmp_path)), ["terror"])
    assert title == "El vecino del sótano" and tags[0] == "terror"
    assert (
        description.startswith("Siempre cerraba")
        and DISCLOSURE in description
        and "#storytime" in description
        and "minecraft" not in description
    )


def test_missing_sidecar_is_explained(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="falta solo.json"):
        load_sidecar(tmp_path / "solo.mp4")


# ------------------------------------------------------------------ YouTube


def test_youtube_body_is_private_scheduled_not_for_kids_and_declares_ai() -> None:
    body = build_upload_body(
        title="T", description="D", tags=["a"], publish_at=NOW + timedelta(days=1)
    )
    assert body["status"] == {
        "privacyStatus": "private",
        "publishAt": "2026-11-03T12:00:00Z",
        "selfDeclaredMadeForKids": False,
        "containsSyntheticMedia": True,
    }
    assert body["snippet"]["title"] == "T" and body["snippet"]["defaultLanguage"] == "es"


def test_youtube_body_validations() -> None:
    with pytest.raises(ValueError, match="100 caracteres"):
        build_upload_body(title="x" * 101, description="", tags=[], publish_at=NOW)
    with pytest.raises(ValueError, match="zona horaria"):
        build_upload_body(title="t", description="", tags=[], publish_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="15 minutos"):
        check_future(NOW + timedelta(minutes=5), NOW)
    check_future(NOW + timedelta(minutes=20), NOW)


# ------------------------------------------------------------------ TikTok


def test_chunk_plan() -> None:
    assert plan_chunks(1000) == [(0, 999)]
    assert plan_chunks(CHUNK) == [(0, CHUNK - 1)]
    three = plan_chunks(CHUNK * 2 + 10)  # 128 MB + 10: dos trozos, el último absorbe el resto
    assert three == [(0, CHUNK - 1), (CHUNK, CHUNK * 2 + 9)]
    assert plan_chunks(154_305_702)[-1][1] == 154_305_701
    with pytest.raises(ValueError):
        plan_chunks(0)


def test_init_body_declares_ai_content_and_the_chunk_layout() -> None:
    body = build_init_body(
        title="T" * 3000, privacy_level="SELF_ONLY", size=1000, is_aigc=True, chunks=[(0, 999)]
    )
    assert body["post_info"]["is_aigc"] is True and len(body["post_info"]["title"]) == 2200
    assert body["source_info"] == {
        "source": "FILE_UPLOAD",
        "video_size": 1000,
        "chunk_size": 1000,
        "total_chunk_count": 1,
    }


def _tiktok_server(statuses: list[str], put_code: int = 201):
    seen: dict[str, Any] = {"puts": [], "init": None, "auth": None}
    answers = iter(statuses)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/post/publish/video/init/":
            seen["init"], seen["auth"] = (
                json.loads(request.content),
                request.headers["Authorization"],
            )
            return httpx.Response(
                200,
                json={
                    "data": {"publish_id": "p1", "upload_url": "https://up.test/u"},
                    "error": {"code": "ok"},
                },
            )
        if request.url.host == "up.test":
            seen["puts"].append((request.headers["Content-Range"], len(request.content)))
            return httpx.Response(put_code)
        if request.url.path == "/v2/post/publish/status/fetch/":
            status = next(answers)
            data = {"status": status, **({"fail_reason": "formato"} if status == "FAILED" else {})}
            return httpx.Response(200, json={"data": data, "error": {"code": "ok"}})
        return httpx.Response(404)

    return seen, httpx.Client(transport=httpx.MockTransport(handler))


def test_tiktok_uploads_the_file_and_waits_for_processing(tmp_path: Path) -> None:
    seen, http = _tiktok_server(["PROCESSING_UPLOAD", "PUBLISH_COMPLETE"])
    client = HttpTikTokClient("tok", http=http, sleep=lambda s: None)
    pid = client.post_video(_video(tmp_path), title="T", privacy_level="SELF_ONLY", is_aigc=True)
    assert pid == "p1" and seen["auth"] == "Bearer tok"
    assert seen["init"]["post_info"]["privacy_level"] == "SELF_ONLY"
    assert seen["puts"] == [("bytes 0-999/1000", 1000)]


def test_tiktok_failures_are_explained(tmp_path: Path) -> None:
    _, http = _tiktok_server(["FAILED"])
    with pytest.raises(TikTokError, match="formato"):
        HttpTikTokClient("t", http=http, sleep=lambda s: None).post_video(
            _video(tmp_path), title="T", privacy_level="SELF_ONLY", is_aigc=True
        )
    _, http = _tiktok_server([], put_code=500)
    with pytest.raises(TikTokError, match="HTTP 500"):
        HttpTikTokClient("t", http=http).post_video(
            _video(tmp_path), title="T", privacy_level="SELF_ONLY", is_aigc=True
        )
    _, http = _tiktok_server(["PROCESSING_UPLOAD"] * 3)
    with pytest.raises(TikTokError, match="tardó demasiado"):
        HttpTikTokClient("t", http=http, sleep=lambda s: None, max_polls=3).post_video(
            _video(tmp_path), title="T", privacy_level="SELF_ONLY", is_aigc=True
        )


def test_tiktok_api_errors_surface_the_code() -> None:
    http = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                401, json={"error": {"code": "access_token_invalid", "message": "caducó"}}
            )
        )
    )
    with pytest.raises(TikTokError, match="access_token_invalid: caducó"):
        HttpTikTokClient("t", http=http).query_creator_info()


# ------------------------------------------------------------------ cola y ejecución


def _queued(tmp_path: Path, youtube_in: timedelta, tiktok_in: timedelta) -> Ledger:
    ledger = Ledger(tmp_path / "q.json")
    video = _video(tmp_path)
    title, description, tags = build_metadata(load_sidecar(video))
    ledger.enqueue(
        video=video,
        platform="youtube",
        title=title,
        description=description,
        tags=tags,
        publish_at=NOW + youtube_in,
    )
    ledger.enqueue(
        video=video,
        platform="tiktok",
        title=title,
        description=description,
        tags=tags,
        publish_at=NOW + tiktok_in,
    )
    return ledger


def test_dry_run_calls_nothing_and_changes_nothing(tmp_path: Path) -> None:
    ledger = _queued(tmp_path, timedelta(days=1), timedelta(days=1))
    yt, tt = FakeYouTube(), FakeTikTok()
    report = run(ledger, NOW, youtube=lambda: yt, tiktok=lambda: tt, live=False)
    assert yt.calls == [] and tt.calls == []
    assert {e.status for e in ledger.entries()} == {"queued"}
    assert (
        report.count("upload") == 1 and report.count("wait") == 1
    )  # YouTube ya; TikTok espera su hora


def test_live_uploads_youtube_now_and_tiktok_only_when_due(tmp_path: Path) -> None:
    ledger = _queued(tmp_path, timedelta(days=1), timedelta(days=1))
    yt, tt = FakeYouTube(), FakeTikTok()

    run(ledger, NOW, youtube=lambda: yt, tiktok=lambda: tt, live=True)

    assert len(yt.calls) == 1 and tt.calls == []
    assert yt.calls[0][0]["status"]["publishAt"] == "2026-11-03T12:00:00Z"
    by = {e.platform: e for e in ledger.entries()}
    assert by["youtube"].status == "uploaded" and by["youtube"].remote_id == "yt123"
    assert by["tiktok"].status == "queued"

    run(
        ledger, NOW + timedelta(days=1, minutes=1), youtube=lambda: yt, tiktok=lambda: tt, live=True
    )

    assert (
        len(tt.calls) == 1 and tt.calls[0]["privacy"] == "SELF_ONLY" and tt.calls[0]["aigc"] is True
    )
    assert {e.status for e in ledger.entries()} == {"uploaded", "published"}


def test_nothing_is_uploaded_twice(tmp_path: Path) -> None:
    ledger = _queued(tmp_path, timedelta(days=1), timedelta(minutes=-1))
    yt, tt = FakeYouTube(), FakeTikTok()
    for _ in range(3):
        run(ledger, NOW, youtube=lambda: yt, tiktok=lambda: tt, live=True)
    assert len(yt.calls) == 1 and len(tt.calls) == 1
    entry = ledger.entries("youtube")[0]
    with pytest.raises(LedgerError, match="ya está en youtube"):
        ledger.enqueue(
            video=Path(entry.video),
            platform="youtube",
            title="t",
            description="d",
            tags=[],
            publish_at=NOW,
        )


def test_a_failure_is_recorded_retried_and_does_not_stop_the_others(tmp_path: Path) -> None:
    ledger = _queued(tmp_path, timedelta(days=1), timedelta(minutes=-1))
    tt = FakeTikTok()
    run(ledger, NOW, youtube=lambda: FakeYouTube(fail=True), tiktok=lambda: tt, live=True)
    by = {e.platform: e for e in ledger.entries()}
    assert by["youtube"].status == "failed" and "ConnectionError" in (by["youtube"].error or "")
    assert by["tiktok"].status == "published"  # la otra plataforma siguió

    healthy = FakeYouTube()
    run(ledger, NOW, youtube=lambda: healthy, live=True)
    assert by["youtube"].status == "uploaded" and by["youtube"].attempts == 2


def test_a_youtube_time_too_close_is_refused_and_recorded(tmp_path: Path) -> None:
    ledger = _queued(tmp_path, timedelta(minutes=3), timedelta(days=1))
    yt = FakeYouTube()
    run(ledger, NOW, youtube=lambda: yt, live=True)
    entry = ledger.entries("youtube")[0]
    assert yt.calls == [] and entry.status == "failed" and "15 minutos" in (entry.error or "")


def test_a_missing_video_file_is_skipped(tmp_path: Path) -> None:
    ledger = _queued(tmp_path, timedelta(days=1), timedelta(days=1))
    Path(ledger.entries()[0].video).unlink()
    assert {a.kind for a in plan(ledger, NOW)} == {"skip"}


def test_the_config_can_change_the_declarations_but_defaults_are_honest() -> None:
    config = PublishConfig()
    assert config.made_for_kids is False and config.synthetic_media is True
    assert config.tiktok_privacy == "SELF_ONLY"


def test_the_queue_survives_a_restart(tmp_path: Path) -> None:
    ledger = _queued(tmp_path, timedelta(days=1), timedelta(days=1))
    ledger.save()
    again = Ledger(tmp_path / "q.json")
    assert [(e.platform, e.status) for e in again.entries()] == [
        ("youtube", "queued"),
        ("tiktok", "queued"),
    ]


# ------------------------------------------------------------------ CLI


def test_cli_enqueue_status_and_dry_run(tmp_path: Path, capsys) -> None:
    video = _video(tmp_path)
    q = str(tmp_path / "queue.json")

    code = main(
        [
            "publish",
            "enqueue",
            str(video),
            "--ledger",
            q,
            "--youtube-at",
            "2099-01-02T18:00",
            "--tiktok-at",
            "2099-01-02T21:00",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert (
        "encolado en youtube" in out and "2099-01-02T23:00:00+00:00" in out
    )  # 18:00 Bogotá = 23:00 UTC

    assert main(["publish", "status", "--ledger", q]) == 0
    assert capsys.readouterr().out.count("queued") == 2

    assert main(["publish", "run", "--ledger", q]) == 0
    out = capsys.readouterr().out
    assert "SIMULACIÓN" in out and "subir y programar" in out and "espera hasta" in out
    assert {e["status"] for e in json.loads(Path(q).read_text(encoding="utf-8"))} == {"queued"}


def test_cli_enqueue_needs_a_time_and_a_sidecar(tmp_path: Path, capsys) -> None:
    video = _video(tmp_path)
    assert main(["publish", "enqueue", str(video), "--ledger", str(tmp_path / "q.json")]) == 1
    assert "--youtube-at" in capsys.readouterr().err
    bare = tmp_path / "solo.mp4"
    bare.write_bytes(b"x")
    assert (
        main(
            [
                "publish",
                "enqueue",
                str(bare),
                "--ledger",
                str(tmp_path / "q.json"),
                "--youtube-at",
                "2099-01-01T10:00",
            ]
        )
        == 1
    )
    assert "falta solo.json" in capsys.readouterr().err


def test_cli_live_without_credentials_fails_and_records_it(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    video = _video(tmp_path)
    q = str(tmp_path / "q.json")
    monkeypatch.delenv("STORYCLIPS_TIKTOK_TOKEN", raising=False)
    main(["publish", "enqueue", str(video), "--ledger", q, "--tiktok-at", "2000-01-01T10:00"])
    capsys.readouterr()

    assert main(["publish", "run", "--ledger", q, "--live"]) == 0

    (entry,) = json.loads(Path(q).read_text(encoding="utf-8"))
    assert entry["status"] == "failed" and "STORYCLIPS_TIKTOK_TOKEN" in entry["error"]


def test_cli_slots(tmp_path: Path, capsys) -> None:
    assert (
        main(
            [
                "publish",
                "slots",
                "--ledger",
                str(tmp_path / "q.json"),
                "--times",
                "10:00",
                "--count",
                "2",
            ]
        )
        == 0
    )
    lines = capsys.readouterr().out.split()
    assert len(lines) == 2 and all(s.endswith("-05:00") for s in lines)


# ------------------------------------------------------------------ varias historias de dos partes


def _story_folder(tmp_path: Path, stories: int = 2) -> Path:
    folder = tmp_path / "out"
    folder.mkdir()
    for n in range(1, stories + 1):
        slug = f"historia-{n}-abc123"
        (folder / f"{slug}.json").write_text(
            json.dumps(
                {
                    "title": f"Historia {n}",
                    "hook": "gancho general",
                    "parts": [
                        {
                            "index": 1,
                            "title": f"Historia {n} (Parte 1/2)",
                            "hook": "Empezó así.",
                            "file": f"{slug}_parte1.mp4",
                        },
                        {
                            "index": 2,
                            "title": f"Historia {n} (Parte 2/2)",
                            "hook": "Y terminó asá.",
                            "file": f"{slug}_parte2.mp4",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        for part in (1, 2):
            (folder / f"{slug}_parte{part}.mp4").write_bytes(b"0" * 100)
    return folder


def test_a_part_uses_its_own_title_and_hook_from_the_story_file(tmp_path: Path) -> None:
    folder = _story_folder(tmp_path, 1)
    first = load_sidecar(folder / "historia-1-abc123_parte1.mp4")
    assert (
        first["title"] == "Historia 1 (Parte 1/2)"
        and first["hook"] == "Empezó así."
        and first["part"] == 1
    )
    _, description, _ = build_metadata(first)
    assert description.startswith("Empezó así.") and "Continúa en la parte 2." in description
    _, last_description, _ = build_metadata(load_sidecar(folder / "historia-1-abc123_parte2.mp4"))
    assert "Continúa" not in last_description


def test_enqueue_all_schedules_every_part_in_consecutive_slots(tmp_path: Path, capsys) -> None:
    folder = _story_folder(tmp_path, 2)
    q = str(tmp_path / "q.json")

    code = main(
        [
            "publish",
            "enqueue-all",
            str(folder),
            "--ledger",
            q,
            "--times",
            "12:00,18:00",
            "--start",
            "2099-03-01T00:00",
        ]
    )

    assert code == 0 and "4 video(s) encolados" in capsys.readouterr().out
    entries = sorted(json.loads(Path(q).read_text(encoding="utf-8")), key=lambda e: e["publish_at"])
    assert [e["title"] for e in entries] == [
        "Historia 1 (Parte 1/2)", "Historia 1 (Parte 2/2)", "Historia 2 (Parte 1/2)", "Historia 2 (Parte 2/2)",
    ]  # fmt: skip
    assert [e["publish_at"][:16] for e in entries][:2] == [
        "2099-03-01T17:00",
        "2099-03-01T23:00",
    ]  # 12:00 y 18:00 Bogotá
    # ejecutarlo otra vez no duplica nada
    assert (
        main(["publish", "enqueue-all", str(folder), "--ledger", q, "--start", "2099-03-01T00:00"])
        == 0
    )
    assert len(json.loads(Path(q).read_text(encoding="utf-8"))) == 4


def test_max_uploads_respects_the_daily_quota(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "q.json")
    for n in range(5):
        video = tmp_path / f"v{n}.mp4"
        video.write_bytes(b"0")
        ledger.enqueue(
            video=video,
            platform="youtube",
            title=f"t{n}",
            description="d",
            tags=[],
            publish_at=NOW + timedelta(days=n + 1),
        )
    yt = FakeYouTube()

    report = run(ledger, NOW, youtube=lambda: yt, live=True, max_uploads=2)

    assert len(yt.calls) == 2 and report.count("upload") == 2 and report.count("wait") == 3
    assert sorted(e.status for e in ledger.entries()).count("queued") == 3
    run(ledger, NOW, youtube=lambda: yt, live=True, max_uploads=2)  # el día siguiente: otras 2
    assert len(yt.calls) == 4


# ------------------------------------------------------------------ hashtags


def test_story_tags_go_first_then_the_format_ones_and_are_capped() -> None:
    sidecar = {
        "title": "T",
        "tags": ["quietfiring", "jefetoxico", "derechoslaborales"],
        "hook": "g",
    }
    _, description, tags = build_metadata(sidecar, ["extra1", "extra2", "extra3"])
    hashtags = description.splitlines()[-1].split()
    assert hashtags[:3] == [
        "#quietfiring",
        "#shorts",
        "#storytime",
    ]  # los 3 que YouTube muestra sobre el título
    assert len(hashtags) == 8 and tags[0] == "quietfiring" and "derechoslaborales" in tags


def test_tags_are_deduplicated_and_never_misleading() -> None:
    _, description, tags = build_metadata(
        {"title": "T", "tags": ["Storytime", "#Shorts", "jefe tóxico"]}
    )
    assert len(tags) == len(set(tags)) and "jefetóxico" in tags
    for forbidden in ("minecraft", "truestory", "historiasreales", "verdadera"):
        assert forbidden not in description.lower() and forbidden not in tags
    assert "ficcion" in tags and DISCLOSURE in description


def test_refresh_updates_only_what_is_still_queued(tmp_path: Path, capsys) -> None:
    folder = _story_folder(tmp_path, 1)
    q = str(tmp_path / "q.json")
    main(["publish", "enqueue-all", str(folder), "--ledger", q, "--start", "2099-03-01T00:00"])
    capsys.readouterr()
    data = json.loads(Path(q).read_text(encoding="utf-8"))
    data[0]["status"], data[0]["description"] = "uploaded", "texto viejo"  # ya subido: no se toca
    data[1]["description"] = "texto viejo"  # sigue en cola: se actualiza
    Path(q).write_text(json.dumps(data), encoding="utf-8")

    assert main(["publish", "refresh", "--ledger", q, "--tags", "nueva"]) == 0

    after = json.loads(Path(q).read_text(encoding="utf-8"))
    assert after[0]["description"] == "texto viejo"
    assert "#shorts" in after[1]["description"] and "nueva" in after[1]["tags"]
    assert "1 entrada(s) actualizadas" in capsys.readouterr().out


def test_reschedule_moves_pending_entries_to_the_future_and_keeps_order(
    tmp_path: Path, capsys
) -> None:
    folder = _story_folder(tmp_path, 2)
    q = str(tmp_path / "q.json")
    main(
        ["publish", "enqueue-all", str(folder), "--ledger", q, "--start", "2000-01-01T00:00"]
    )  # horarios ya vencidos
    capsys.readouterr()
    data = json.loads(Path(q).read_text(encoding="utf-8"))
    data[0]["status"] = "uploaded"
    data[1]["status"], data[1]["error"] = (
        "failed",
        "ValueError: publish_at debe quedar en el futuro",
    )
    Path(q).write_text(json.dumps(data), encoding="utf-8")
    uploaded_when = data[0]["publish_at"]

    assert main(["publish", "reschedule", "--ledger", q, "--times", "12:00,18:00"]) == 0

    after = json.loads(Path(q).read_text(encoding="utf-8"))
    assert (
        after[0]["publish_at"] == uploaded_when and after[0]["status"] == "uploaded"
    )  # lo subido no se toca
    pending = after[1:]
    assert all(e["status"] == "queued" and e["error"] is None for e in pending)
    whens = [e["publish_at"] for e in pending]
    assert whens == sorted(whens) and whens[0] > datetime.now(UTC).isoformat()
    assert "3 entrada(s) reprogramadas" in capsys.readouterr().out
