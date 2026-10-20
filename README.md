# storyclips

Videos verticales (9:16) de **historias originales** narradas con voz en off sobre **tus propios** videos de
fondo (por ejemplo tu gameplay de Minecraft). Cada historia se corta en **dos partes en el momento más
tenso**: la parte 1 termina con la tarjeta «Parte 2 en el siguiente video» para que quien la vea quiera ver la
siguiente.

Qué hace: LLM (Qwen por API u Ollama) escribe la historia -> Kokoro (local) la narra -> subtítulos palabra por
palabra -> FFmpeg monta fondo + voz + subtítulos. No sube nada todavía.

Qué NO hace, a propósito: no descarga ni copia historias de Reddit ni de ninguna web (son texto de terceros);
las historias son originales. Los fondos son solo los de tu carpeta `backgrounds/`.

## Instalación

```bash
winget install Gyan.FFmpeg          # ffmpeg y ffprobe en el PATH
uv sync --extra tts                 # kokoro-onnx + numpy (voz local, CPU)
```

Voz: descarga tú `kokoro-v1.0.onnx` y `voices-v1.0.bin` desde la página oficial de kokoro-onnx y déjalos en
`models/` (o apunta `STORYCLIPS_KOKORO_MODEL` / `STORYCLIPS_KOKORO_VOICES`). Revisa su licencia vigente.

LLM (cualquier endpoint compatible con OpenAI):

```bash
# Ollama local (por defecto): ollama pull qwen2.5:7b
# Qwen por API (DashScope u OpenRouter): define
set STORYCLIPS_LLM_BASE_URL=https://.../v1
set STORYCLIPS_LLM_MODEL=qwen-plus
set STORYCLIPS_LLM_API_KEY=...
```

## Uso

```bash
# 1. pon tus videos largos en backgrounds/ (mp4, mkv, mov, webm)
uv run storyclips render --help
uv run storyclips batch --topic "un vecino que oculta algo en el sótano" --count 3
uv run storyclips batch --topics-file temas.txt          # un tema por línea
uv run storyclips write --topic "..." && uv run storyclips render stories/*.json
uv run storyclips render stories/x.json --fake-tts      # prueba sin modelo de voz
```

Salida en `out/`: `<historia>_parte1.mp4`, `<historia>_parte2.mp4` y `<historia>.json` con los títulos de cada
parte. Voz en inglés: `--voice af_heart --tts-lang en-us`; historias en inglés: `--language English`.

## Notas

- El audio del juego se descarta: solo suena la voz (evita música con derechos).
- El corte lo marca el LLM con `[CORTE]`; si no lo pone, se corta cerca del 60 % en una frase de gancho.
- Publicidad de voz sintética: marca los videos como contenido alterado/sintético donde la plataforma lo pida.
- Pendiente: subir a YouTube/TikTok (el publicador de kidsgen se puede adaptar; TikTok exige su propia API y
  auditoría), música de fondo opcional, varias voces.

## En Hypatia (SLURM + GPU) — la forma de uso real

Todo corre en un job con 1 GPU: Qwen (vLLM) escribe las historias, Kokoro las narra y FFmpeg monta los
videos. Los nodos de cómputo normalmente NO tienen internet, así que los pesos se bajan antes desde el login.
Los valores de partición, GPU y rutas son **provisionales: confírmalos con la administración de Hypatia**.

```bash
# En el nodo de login (con internet), una sola vez:
git clone <tu repo> storyclips && cd storyclips          # o súbelo con scp/rsync
export STORYCLIPS_MODELS=/project/models
bash hpc/prepare_models.sh                                # Qwen2.5-7B-Instruct + Kokoro
apptainer build --fakeroot /project/storyclips/storyclips.sif hpc/storyclips.def

# Tus datos (desde tu PC): videos de fondo y temas
#   /project/storyclips/backgrounds/*.mp4     (tus videos de Minecraft, varios minutos cada uno)
#   /project/storyclips/topics.txt            (un tema por línea)

# Lanzar:
sbatch --partition=<gpu> --gres=gpu:1 hpc/storyclips.sbatch
```

Resultado en `/project/storyclips/runs/<jobid>/out/` (`*_parte1.mp4`, `*_parte2.mp4`, `*.json`) y los logs en
`vllm.log` y `storyclips-<jobid>.out`. Variables útiles al lanzar (`--export=ALL,CLAVE=valor`): `STORY_LANGUAGE`,
`TTS_VOICE`, `TTS_LANG`, `LLM_DIR`, `TP_SIZE` (más de 1 GPU para un modelo grande).

Qué falta confirmar en Hypatia: que haya Apptainer y `--fakeroot` para construir (si no, construye la imagen en
otra máquina y súbela), versión de CUDA/driver compatible con la imagen de vLLM (fija su etiqueta en
`hpc/storyclips.def`), y la partición y GPU a usar. Una historia a la vez; si necesitas cientos, el siguiente
paso es paralelizar las peticiones a vLLM.
