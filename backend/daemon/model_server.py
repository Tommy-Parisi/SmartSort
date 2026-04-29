"""
Lightweight local HTTP model server — loads sentence-transformers once,
serves embeddings to any local process.

GET  /health       →  {"status": "ok", "model": "<name>"}
POST /embed        →  {"text": "..."}          →  {"embedding": [...]}
POST /embed_batch  →  {"texts": ["...", ...]}  →  {"embeddings": [[...], ...]}

Start from daemon_runner.py before watchdog so the pipeline subprocess
can share model weights via localhost instead of loading a second copy.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

MODEL_SERVER_PORT = 7234
MODEL_SERVER_URL = f"http://127.0.0.1:{MODEL_SERVER_PORT}"
_DEFAULT_MODEL = "all-MiniLM-L6-v2"


class _EmbedHandler(BaseHTTPRequestHandler):
    server: "_ModelHTTPServer"

    def log_message(self, format, *args):
        pass  # silence per-request access log

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "model": self.server.model_name})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/embed_batch":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body)
                texts = [str(t) for t in payload.get("texts", [])]
            except Exception:
                self._send_json(400, {"error": "invalid JSON"})
                return
            try:
                with self.server.lock:
                    vecs = self.server.model.encode(texts, convert_to_numpy=True)
                self._send_json(200, {"embeddings": vecs.tolist()})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        if self.path != "/embed":
            self._send_json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
            text = str(payload.get("text", ""))
        except Exception:
            self._send_json(400, {"error": "invalid JSON"})
            return

        try:
            with self.server.lock:
                vec = self.server.model.encode(text, convert_to_numpy=True)
            self._send_json(200, {"embedding": vec.tolist()})
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})

    def _send_json(self, code: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _ModelHTTPServer(HTTPServer):
    def __init__(self, model_name: str, port: int):
        super().__init__(("127.0.0.1", port), _EmbedHandler)
        self.model_name = model_name
        self.lock = threading.Lock()
        from sentence_transformers import SentenceTransformer
        print(f"[ModelServer] Loading {model_name}…")
        self.model = SentenceTransformer(model_name)
        print(f"[ModelServer] Model ready.")


class ModelServer:
    """Manages a background-thread HTTP server for model inference."""

    def __init__(self, model_name: str = _DEFAULT_MODEL, port: int = MODEL_SERVER_PORT):
        self.model_name = model_name
        self.port = port
        self._server: Optional[_ModelHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._server = _ModelHTTPServer(self.model_name, self.port)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="model-server",
        )
        self._thread.start()
        print(f"[ModelServer] Listening on 127.0.0.1:{self.port}")

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None
        print("[ModelServer] Stopped.")
