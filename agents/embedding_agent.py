from sentence_transformers import SentenceTransformer
from core.models import FileContent, EmbeddedFile
from core.utils import log_error

class EmbeddingAgent:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def embed(self, file: FileContent) -> EmbeddedFile:
        if file.status != "success":
            return EmbeddedFile(file_meta=file.file_meta, embedding=None, raw_text="", status="error")

        text = file.raw_text.strip()
        if len(text.split()) < 5:
            return EmbeddedFile(file_meta=file.file_meta, embedding=None, raw_text=text, status="too_short")

        try:
            vector = self.model.encode(text, convert_to_numpy=True)
            return EmbeddedFile(file_meta=file.file_meta, embedding=vector.tolist(), raw_text=text, status="embedded")
        except Exception as e:
            log_error(f"[EmbeddingAgent] Failed to embed {file.file_meta.file_name}: {e}")
            return EmbeddedFile(file_meta=file.file_meta, embedding=None, raw_text=text, status="error")