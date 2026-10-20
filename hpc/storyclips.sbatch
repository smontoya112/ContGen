#!/bin/bash
# Una corrida completa: historias con Qwen (vLLM) + voz Kokoro + video con FFmpeg, en 1 GPU.
#
# Los valores de abajo son PROVISIONALES: cámbialos al lanzar con la partición y GPU reales de Hypatia,
#   sbatch --partition=<la-tuya> --gres=gpu:<tipo>:1 hpc/storyclips.sbatch
# (las directivas #SBATCH no leen variables de entorno).
#SBATCH --job-name=storyclips
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=%x-%j.out

set -euo pipefail

PROJECT="${STORYCLIPS_PROJECT:-/project/storyclips}"   # backgrounds/, topics.txt, runs/ y la imagen
MODELS="${STORYCLIPS_MODELS:-/project/models}"        # qwen2.5-7b-instruct/ y kokoro/
IMAGE="${STORYCLIPS_IMAGE:-$PROJECT/storyclips.sif}"

mkdir -p "$PROJECT/runs"

# --nv expone la GPU. El contenedor no necesita red: los pesos ya están en $MODELS.
apptainer exec --nv \
    --bind "$PROJECT:/data,$MODELS:/models" \
    "$IMAGE" \
    bash /opt/storyclips/hpc/run_batch.sh
