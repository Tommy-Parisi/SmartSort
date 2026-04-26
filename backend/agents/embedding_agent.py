from ..core.models import FileContent, EmbeddedFile
from ..core.utils import log_error
from ..core.constants import SKIP_EMBEDDING_TYPES, MIN_TOKENS_TO_EMBED
from .identity_utils import build_identity_text

_MAX_CHARS = 2000  # ~256 tokens for all-MiniLM-L6-v2; avoids tokenizing huge strings
_PHOTO_PREFIX = "__PHOTO__"

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


class EmbeddingAgent:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._use_server = _server_healthy()
        if self._use_server:
            self.model = None
        else:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)

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

    def embed(self, file: FileContent) -> EmbeddedFile:
        if file.status != "success":
            return EmbeddedFile(file_meta=file.file_meta, embedding=None, raw_text="", status="error")

        # Media/archive types never produce meaningful cluster signal
        if file.file_meta.detected_type in SKIP_EMBEDDING_TYPES:
            return EmbeddedFile(file_meta=file.file_meta, embedding=None, raw_text="", status="skipped")

        raw = file.raw_text.strip()

        # Camera photos carry a date bucket, not semantic text — route to photo clusters
        if raw.startswith(_PHOTO_PREFIX):
            date_bucket = raw[len(_PHOTO_PREFIX):]
            return EmbeddedFile(
                file_meta=file.file_meta,
                embedding=None,
                raw_text=date_bucket,
                status="photo",
            )

        # Prepend doctype prefix and strip filename noise before encoding.
        # "resume: thomas parisi python react..." embeds far from
        # "agreement: university health plan coverage..." even if their
        # raw text has overlapping tokens.
        text = build_identity_text(file.file_meta.file_name, raw)[:_MAX_CHARS]

        # Near-empty extractions produce near-random embeddings that pollute clusters
        if len(text.split()) < MIN_TOKENS_TO_EMBED:
            return EmbeddedFile(file_meta=file.file_meta, embedding=None, raw_text=raw, status="too_short")

        try:
            vector = self._encode(text)
            return EmbeddedFile(file_meta=file.file_meta, embedding=vector, raw_text=text, status="embedded")
        except Exception as e:
            log_error(f"[EmbeddingAgent] Failed to embed {file.file_meta.file_name}: {e}")
            return EmbeddedFile(file_meta=file.file_meta, embedding=None, raw_text=text, status="error")
