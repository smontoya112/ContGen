#!/bin/bash
# Córrelo en el NODO DE LOGIN (los nodos de cómputo normalmente no tienen internet).
# Descarga los pesos una sola vez a $MODELS. Revisa antes la licencia vigente de cada modelo.
set -euo pipefail

MODELS="${STORYCLIPS_MODELS:-/project/models}"
LLM_REPO="${LLM_REPO:-Qwen/Qwen2.5-7B-Instruct}"
KOKORO_BASE="${KOKORO_BASE:-https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0}"

mkdir -p "$MODELS/kokoro"

echo "LLM: $LLM_REPO"
# Necesita `pip install -U "huggingface_hub[cli]"` (en un venv de tu usuario).
huggingface-cli download "$LLM_REPO" --local-dir "$MODELS/qwen2.5-7b-instruct"

echo "Kokoro (voz)"
for f in kokoro-v1.0.onnx voices-v1.0.bin; do
    [ -f "$MODELS/kokoro/$f" ] || curl -fL --retry 3 -o "$MODELS/kokoro/$f" "$KOKORO_BASE/$f"
done

echo "Listo en $MODELS:"
du -sh "$MODELS"/*
