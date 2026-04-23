from backend.agents.embedding_agent import EmbeddingAgent
from backend.core.models import FileContent, FileMeta


def _meta(name: str, detected_type: str) -> FileMeta:
    return FileMeta(
        file_path=f"/tmp/{name}",
        file_name=name,
        extension=".png" if detected_type == "image" else ".txt",
        detected_type=detected_type,
        size_kb=1.0,
        created_at="2024-01-01T00:00:00",
        modified_at="2024-01-01T00:00:00",
    )


def test_image_files_are_embedded_when_identity_has_signal():
    agent = EmbeddingAgent.__new__(EmbeddingAgent)
    agent._use_server = False
    agent._encode = lambda text: [0.1, 0.2, 0.3]

    content = FileContent(
        file_meta=_meta("scan.png", "image"),
        raw_text="agreement: scanned document university health plan coverage benefits policy",
        status="success",
    )

    embedded = EmbeddingAgent.embed(agent, content)
    assert embedded.status == "embedded"
    assert embedded.embedding == [0.1, 0.2, 0.3]
