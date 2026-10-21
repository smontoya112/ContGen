#!/bin/bash
# Corrida completa dentro de un nodo con GPU (Hypatia): Qwen escribe, Kokoro narra, FFmpeg monta.
# Estructura esperada en el repo (~/ContGen):
#   venv/ (storyclips + Kokoro)  venv-llm/ (torch cu118 + transformers)  bin/ (ffmpeg, ffprobe)
#   espeak/ (espeak-ng compilado)  models/ (qwen2.5-7b-instruct, kokoro)  data/ (backgrounds, topics.txt, runs)
#
# Lanzar (pidiendo la GPU):
#   srun --mem=64gb --cpus-per-task=8 --time=02:00:00 --gres=gpu:1 -p gpu bash hpc/run_server.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$REPO/bin:$PATH"
# shellcheck disable=SC1091
source "$REPO/venv/bin/activate"

export LLM_PYTHON="${LLM_PYTHON:-$REPO/venv-llm/bin/python}"
export DATA_DIR="${DATA_DIR:-$REPO/data}" MODELS_DIR="${MODELS_DIR:-$REPO/models}"
export PHONEMIZER_ESPEAK_LIBRARY="${PHONEMIZER_ESPEAK_LIBRARY:-$REPO/espeak/lib/libespeak-ng.so}"
export ESPEAK_DATA_PATH="${ESPEAK_DATA_PATH:-$REPO/espeak/share/espeak-ng-data}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

exec bash "$REPO/hpc/run_batch.sh"
