#!/bin/bash
# Una corrida completa en el servidor: Qwen (vLLM) escribe, Kokoro narra, FFmpeg monta.
# Para dejarla corriendo aunque cierres la sesión:  nohup bash hpc/run_server.sh > corrida.log 2>&1 &
set -euo pipefail

ROOT="${STORYCLIPS_HOME:-$HOME/storyclips-data}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

# shellcheck disable=SC1091
source "$ROOT/venv/bin/activate"
export DATA_DIR="$ROOT" MODELS_DIR="$ROOT/models"
exec bash "$REPO/hpc/run_batch.sh"
