#!/bin/bash
# Corre DENTRO del contenedor, dentro de un job de SLURM con 1 GPU.
# 1) levanta vLLM con Qwen en localhost, 2) escribe las historias de topics.txt, 3) apaga vLLM,
# 4) narra y monta los videos. Todo lo que necesita está montado: /data (proyecto) y /models (pesos).
set -euo pipefail

DATA="${DATA_DIR:-/data}"        # sin contenedor: DATA_DIR y MODELS_DIR apuntan a carpetas reales
MODELS="${MODELS_DIR:-/models}"
RUN="$DATA/runs/${SLURM_JOB_ID:-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$RUN/stories" "$RUN/out"

LLM_DIR="${LLM_DIR:-$MODELS/qwen2.5-7b-instruct}"
PORT="${VLLM_PORT:-8000}"
TOPICS="${TOPICS_FILE:-$DATA/topics.txt}"
BACKGROUNDS="${BACKGROUNDS_DIR:-$DATA/backgrounds}"

export STORYCLIPS_LLM_BASE_URL="http://127.0.0.1:${PORT}/v1"
export STORYCLIPS_LLM_MODEL="qwen"
export STORYCLIPS_KOKORO_MODEL="${STORYCLIPS_KOKORO_MODEL:-$MODELS/kokoro/kokoro-v1.0.onnx}"
export STORYCLIPS_KOKORO_VOICES="${STORYCLIPS_KOKORO_VOICES:-$MODELS/kokoro/voices-v1.0.bin}"

[ -f "$TOPICS" ] || { echo "ERROR: falta $TOPICS (un tema por línea)" >&2; exit 2; }
[ -d "$LLM_DIR" ] || { echo "ERROR: faltan los pesos del LLM en $LLM_DIR (corre hpc/prepare_models.sh)" >&2; exit 2; }

echo "[$(date +%T)] arrancando vLLM ($LLM_DIR)"
# LLM_BACKEND=hf (por defecto): transformers + PyTorch cu118, para GPU/driver antiguos como los de
# Hypatia (Quadro RTX 6000, CUDA 11.8). LLM_BACKEND=vllm: vLLM, solo con driver/CUDA 12 o más.
if [ "${LLM_BACKEND:-hf}" = "vllm" ]; then
    python3 -m vllm.entrypoints.openai.api_server \
        --model "$LLM_DIR" --served-model-name qwen --port "$PORT" \
        --max-model-len 4096 --gpu-memory-utilization "${GPU_MEM_UTIL:-0.85}" \
        --tensor-parallel-size "${TP_SIZE:-1}" > "$RUN/vllm.log" 2>&1 &
else
    "${LLM_PYTHON:-python3}" "$(dirname "$0")/hf_server.py" \
        --model "$LLM_DIR" --served-model-name qwen --port "$PORT" > "$RUN/vllm.log" 2>&1 &
fi
VLLM_PID=$!
trap 'kill "$VLLM_PID" 2>/dev/null || true' EXIT

# Espera a que el servidor responda (cargar los pesos tarda minutos); sin curl: usa Python.
python3 - "$PORT" "$VLLM_PID" <<'PY'
import os, sys, time, urllib.request
port, pid = sys.argv[1], int(sys.argv[2])
for _ in range(180):
    try:
        os.kill(pid, 0)
    except OSError:
        sys.exit("vLLM terminó antes de estar listo: revisa vllm.log")
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3)
        sys.exit(0)
    except Exception:
        time.sleep(5)
sys.exit("vLLM no respondió en 15 minutos")
PY

echo "[$(date +%T)] escribiendo historias"
storyclips write --topics-file "$TOPICS" --stories "$RUN/stories" --language "${STORY_LANGUAGE:-español neutro}"

echo "[$(date +%T)] apagando vLLM para liberar la GPU"
kill "$VLLM_PID" 2>/dev/null || true
wait "$VLLM_PID" 2>/dev/null || true

echo "[$(date +%T)] narrando y montando"
storyclips render "$RUN"/stories/*.json --backgrounds "$BACKGROUNDS" --out "$RUN/out" \
    --voice "${TTS_VOICE:-ef_dora}" --tts-lang "${TTS_LANG:-es}" \
    --parts "${PARTS:-2}" ${ALLOW_LOOP:+--allow-loop}

echo "[$(date +%T)] listo: $RUN/out"
