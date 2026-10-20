#!/bin/bash
# Instalación en un servidor Linux con GPU NVIDIA (sin SLURM ni contenedores). Córrelo una vez.
# Requisitos: driver NVIDIA funcionando (`nvidia-smi`), Python 3.10-3.12, internet, ffmpeg.
set -euo pipefail

ROOT="${STORYCLIPS_HOME:-$HOME/storyclips-data}"     # videos de fondo, temas, modelos y salidas
REPO="$(cd "$(dirname "$0")/.." && pwd)"

nvidia-smi -L || { echo "ERROR: no veo la GPU (nvidia-smi falló)" >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo "ERROR: instala ffmpeg (sudo apt install ffmpeg)" >&2; exit 1; }
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

mkdir -p "$ROOT"/{backgrounds,models,runs}
cd "$REPO"
uv venv --python 3.11 "$ROOT/venv"
# shellcheck disable=SC1091
source "$ROOT/venv/bin/activate"
uv pip install -e ".[tts]" vllm "huggingface_hub[cli]"

STORYCLIPS_MODELS="$ROOT/models" bash "$REPO/hpc/prepare_models.sh"

[ -f "$ROOT/topics.txt" ] || printf '# un tema por línea\nun vecino que oculta algo en el sótano\n' > "$ROOT/topics.txt"
echo
echo "Listo. Pon tus videos de fondo en $ROOT/backgrounds/ y corre: bash hpc/run_server.sh"
