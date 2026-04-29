import pickle
import time
from pathlib import Path

from ..core.models import FileContent, EmbeddedFile
from ..core.utils import log_error
from ..core.constants import SKIP_EMBEDDING_TYPES, MIN_TOKENS_TO_EMBED
from .identity_utils import build_identity_text

_MAX_CHARS = 2000  # ~256 tokens for all-MiniLM-L6-v2; avoids tokenizing huge strings
_PHOTO_PREFIX      = "__PHOTO__"
_SCREENSHOT_PREFIX = "__SCREENSHOT__"

_CACHE_PATH = Path.home() / ".smartsort" / "embedding_cache.pkl"
_PID_FILE   = Path.home() / ".smartsort" / "daemon.pid"

try:
    from ..daemon.model_server import MODEL_SERVER_URL
except ImportError:
    MODEL_SERVER_URL = "http://127.0.0.1:7234"


def _server_healthy() -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen(f"{MODEL_SERVER_URL}/health", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


def _wait_for_server(timeout: float = 10.0) -> bool:
    """Return True if server becomes healthy within timeout.

    Only waits if a daemon PID file exists; otherwise falls through immediately
    so cold starts with no daemon don't add latency.
    """
    if _server_healthy():
        return True
    if not _PID_FILE.exists():
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(0.5)
        if _server_healthy():
            return True
    return False


def _load_cache() -> dict:
    try:
        if _CACHE_PATH.exists():
            with open(_CACHE_PATH, "rb") as f:
                return pickle.load(f)
    except Exception:
        pass
    return {}


def _save_cache(cache: dict) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_PATH, "wb") as f:
            pickle.dump(cache, f, protocol=4)
    except Exception:
        pass


class EmbeddingAgent:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._use_server = _wait_for_server()
        if self._use_server:
            self.model = None
        else:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
        self._cache = _load_cache()

    # ── single-file encode (kept for daemon/assignment use) ──────────────────

    def _encode(self, text: str) -> list:
        if self._use_server:
            import json, urllib.request
            body = json.dumps({"text": text}).encode()
            req = urllib.request.Request(
                f"{MODEL_SERVER_URL}/embed",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())["embedding"]
        return self.model.encode(text, convert_to_numpy=True).tolist()

    # ── batch encode ──────────────────────────────────────────────────────────

    def _encode_batch(self, texts: list) -> list:
        """Encode a list of texts in one model call. Returns list-of-lists."""
        if self._use_server:
            import json, urllib.request
            body = json.dumps({"texts": texts}).encode()
            req = urllib.request.Request(
                f"{MODEL_SERVER_URL}/embed_batch",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())["embeddings"]
        vecs = self.model.encode(texts, convert_to_numpy=True)
        return vecs.tolist()

    # ── public API ────────────────────────────────────────────────────────────

    def embed(self, file: FileContent) -> EmbeddedFile:
        """Embed a single file. Used by the daemon assignment path."""
        if file.status != "success":
            return EmbeddedFile(file_meta=file.file_meta, embedding=None, raw_text="", status="error")

        if file.file_meta.detected_type in SKIP_EMBEDDING_TYPES:
            return EmbeddedFile(file_meta=file.file_meta, embedding=None, raw_text="", status="skipped")

        raw = file.raw_text.strip()

        if raw.startswith(_SCREENSHOT_PREFIX):
            return EmbeddedFile(
                file_meta=file.file_meta, embedding=None, raw_text="screenshot", status="screenshot"
            )

        if raw.startswith(_PHOTO_PREFIX):
            date_bucket = raw[len(_PHOTO_PREFIX):]
            return EmbeddedFile(
                file_meta=file.file_meta, embedding=None, raw_text=date_bucket, status="photo"
            )

        text = build_identity_text(file.file_meta.file_name, raw)[:_MAX_CHARS]

        if len(text.split()) < MIN_TOKENS_TO_EMBED:
            return EmbeddedFile(file_meta=file.file_meta, embedding=None, raw_text=raw, status="too_short")

        cache_key = (file.file_meta.file_path, file.file_meta.modified_at)
        if cache_key in self._cache:
            return EmbeddedFile(
                file_meta=file.file_meta, embedding=self._cache[cache_key], raw_text=text, status="embedded"
            )

        try:
            vector = self._encode(text)
            self._cache[cache_key] = vector
            _save_cache(self._cache)
            return EmbeddedFile(file_meta=file.file_meta, embedding=vector, raw_text=text, status="embedded")
        except Exception as e:
            log_error(f"[EmbeddingAgent] Failed to embed {file.file_meta.file_name}: {e}")
            return EmbeddedFile(file_meta=file.file_meta, embedding=None, raw_text=text, status="error")

    def embed_many(self, files: list) -> list:
        """Batch-embed a list of FileContent objects.

        Pre-routes photos/screenshots/skips without touching the model, then
        encodes all remaining texts in a single model.encode() call (or one
        HTTP round-trip to the model server). Cache hits are resolved before
        the batch so repeat sorts are nearly instant.
        """
        results = [None] * len(files)
        to_encode = []  # (index, text, file, cache_key)

        for i, file in enumerate(files):
            if file.status != "success":
                results[i] = EmbeddedFile(file_meta=file.file_meta, embedding=None, raw_text="", status="error")
                continue

            if file.file_meta.detected_type in SKIP_EMBEDDING_TYPES:
                results[i] = EmbeddedFile(file_meta=file.file_meta, embedding=None, raw_text="", status="skipped")
                continue

            raw = file.raw_text.strip()

            if raw.startswith(_SCREENSHOT_PREFIX):
                results[i] = EmbeddedFile(
                    file_meta=file.file_meta, embedding=None, raw_text="screenshot", status="screenshot"
                )
                continue

            if raw.startswith(_PHOTO_PREFIX):
                date_bucket = raw[len(_PHOTO_PREFIX):]
                results[i] = EmbeddedFile(
                    file_meta=file.file_meta, embedding=None, raw_text=date_bucket, status="photo"
                )
                continue

            text = build_identity_text(file.file_meta.file_name, raw)[:_MAX_CHARS]

            if len(text.split()) < MIN_TOKENS_TO_EMBED:
                results[i] = EmbeddedFile(file_meta=file.file_meta, embedding=None, raw_text=raw, status="too_short")
                continue

            cache_key = (file.file_meta.file_path, file.file_meta.modified_at)
            if cache_key in self._cache:
                results[i] = EmbeddedFile(
                    file_meta=file.file_meta, embedding=self._cache[cache_key], raw_text=text, status="embedded"
                )
                continue

            to_encode.append((i, text, file, cache_key))

        if to_encode:
            texts = [t for _, t, _, _ in to_encode]
            try:
                vectors = self._encode_batch(texts)
                for j, (i, text, file, cache_key) in enumerate(to_encode):
                    vec = vectors[j]
                    self._cache[cache_key] = vec
                    results[i] = EmbeddedFile(
                        file_meta=file.file_meta, embedding=vec, raw_text=text, status="embedded"
                    )
            except Exception as e:
                for i, text, file, cache_key in to_encode:
                    log_error(f"[EmbeddingAgent] Failed to embed {file.file_meta.file_name}: {e}")
                    results[i] = EmbeddedFile(
                        file_meta=file.file_meta, embedding=None, raw_text=text, status="error"
                    )
            _save_cache(self._cache)

        return results
