from dataclasses import dataclass

@dataclass
class FileMeta:
    file_path: str
    file_name: str
    extension: str
    detected_type: str
    size_kb: float
    created_at: str
    modified_at: str
    status: str = "pending"

@dataclass
class FileContent:
    file_meta: FileMeta
    raw_text: str
    status: str = "success"

@dataclass
class EmbeddedFile:
    file_meta: FileMeta
    embedding: list
    raw_text: str
    status: str = "embedded"
