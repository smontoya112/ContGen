from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from storyclips.cli import main

HPC = Path(__file__).resolve().parent.parent / "hpc"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash no disponible")
@pytest.mark.parametrize("script", ["run_batch.sh", "prepare_models.sh", "storyclips.sbatch"])
def test_hpc_scripts_have_valid_bash_syntax(script: str) -> None:
    result = subprocess.run(["bash", "-n", script], cwd=HPC, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_the_sbatch_is_the_documented_one() -> None:
    text = (HPC / "storyclips.sbatch").read_text(encoding="utf-8")
    assert "#SBATCH --gres=gpu:1" in text and "apptainer exec --nv" in text
    assert "/opt/storyclips/hpc/run_batch.sh" in text
    run = (HPC / "run_batch.sh").read_text(encoding="utf-8")
    assert "vllm.entrypoints.openai.api_server" in run and "HF_HUB_OFFLINE" in (
        HPC / "storyclips.def"
    ).read_text(encoding="utf-8")
    assert "storyclips render" in run and "kill" in run  # apaga vLLM antes de renderizar


def test_a_failing_story_does_not_stop_the_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from storyclips import cli
    from storyclips.llm import StoryError
    from storyclips.models import Story

    class Writer:
        def __init__(self, *a, **k) -> None:
            pass

        def write(self, topic: str) -> Story:
            if topic == "malo":
                raise StoryError("sin historia")
            return Story(f"Historia de {topic}", "Una frase. " * 10)

    monkeypatch.setattr(cli, "StoryWriter", Writer)
    monkeypatch.setattr(cli, "ChatClient", lambda c: None)
    topics = tmp_path / "temas.txt"
    topics.write_text("# comentario\nbueno\nmalo\notro\n", encoding="utf-8")

    code = main(["write", "--topics-file", str(topics), "--stories", str(tmp_path / "s")])

    assert code == 0
    files = sorted((tmp_path / "s").glob("*.json"))
    assert len(files) == 2 and json.loads(files[0].read_text(encoding="utf-8"))["topic"] in {
        "bueno",
        "otro",
    }
    assert "sin historia para 'malo'" in capsys.readouterr().err


def test_a_batch_where_everything_fails_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from storyclips import cli
    from storyclips.llm import StoryError

    class Writer:
        def __init__(self, *a, **k) -> None:
            pass

        def write(self, topic: str):
            raise StoryError("nada")

    monkeypatch.setattr(cli, "StoryWriter", Writer)
    monkeypatch.setattr(cli, "ChatClient", lambda c: None)

    assert main(["write", "--topic", "x", "--stories", str(tmp_path)]) == 1
    assert "ninguna historia" in capsys.readouterr().err
