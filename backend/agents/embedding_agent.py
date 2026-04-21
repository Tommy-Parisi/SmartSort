from ..core.models import FileContent, EmbeddedFile
from ..core.utils import log_error

_MAX_CHARS = 2000  # ~256 tokens for all-MiniLM-L6-v2; avoids tokenizing huge strings

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

        text = file.raw_text.strip()[:_MAX_CHARS]
        if len(text.split()) < 5:
            return EmbeddedFile(file_meta=file.file_meta, embedding=None, raw_text=text, status="too_short")

        try:
            vector = self._encode(text)
            return EmbeddedFile(file_meta=file.file_meta, embedding=vector, raw_text=text, status="embedded")
        except Exception as e:
            log_error(f"[EmbeddingAgent] Failed to embed {file.file_meta.file_name}: {e}")
            return EmbeddedFile(file_meta=file.file_meta, embedding=None, raw_text=text, status="error")
