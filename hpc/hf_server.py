"""Servidor mínimo compatible con OpenAI (/v1/chat/completions) sobre transformers.

Existe porque en Hypatia (Quadro RTX 6000, driver 520 = CUDA 11.8) no corren las versiones actuales de
vLLM ni de Ollama (exigen CUDA 12+). Usa PyTorch con CUDA 11.8 y los pesos ya descargados. Atiende una
petición a la vez, suficiente para escribir historias en lote. Turing no soporta bfloat16: usa float16.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def load(path: str):
    tokenizer = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, torch_dtype=torch.float16, device_map="cuda")
    model.eval()
    return tokenizer, model


def make_handler(tokenizer, model, name: str, max_new_tokens: int):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, payload: dict | None = None) -> None:
            body = json.dumps(payload or {}).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            self._send(200 if self.path in ("/health", "/v1/models") else 404)

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/chat/completions":
                return self._send(404)
            try:
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                prompt = tokenizer.apply_chat_template(
                    request["messages"], tokenize=False, add_generation_prompt=True
                )
                inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
                temperature = float(request.get("temperature", 0.7))
                with torch.no_grad():
                    out = model.generate(
                        **inputs,
                        max_new_tokens=int(request.get("max_tokens") or max_new_tokens),
                        do_sample=temperature > 0,
                        temperature=max(temperature, 1e-3),
                        top_p=0.9,
                    )
                text = tokenizer.decode(
                    out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
                )
                print(f"respuesta ({len(text.split())} palabras): {text[:700]!r}", flush=True)
                self._send(
                    200,
                    {
                        "id": "chatcmpl-local",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": name,
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": text},
                                "finish_reason": "stop",
                            }
                        ],
                    },
                )
            except Exception as exc:  # el cliente ve el motivo en vez de una conexión rota
                print(f"error: {exc!r}", file=sys.stderr, flush=True)
                self._send(500, {"error": str(exc)})

        def log_message(self, fmt: str, *args) -> None:
            print(fmt % args, flush=True)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--served-model-name", default="qwen")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--max-new-tokens", type=int, default=1500)
    args = parser.parse_args()
    tokenizer, model = load(args.model)
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port),
        make_handler(tokenizer, model, args.served_model_name, args.max_new_tokens),
    )
    print(f"listo en 127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
