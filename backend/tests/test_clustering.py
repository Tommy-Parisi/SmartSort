import numpy as np

from backend.agents.clustering_agent import ClusteringAgent
from backend.core.models import EmbeddedFile, FileMeta


def _embedded(name: str, identity: str, embedding: list[float]) -> EmbeddedFile:
    meta = FileMeta(
        file_path=f"/tmp/{name}",
        file_name=name,
        extension=".txt",
        detected_type="text",
        size_kb=1.0,
        created_at="2024-01-01T00:00:00",
        modified_at="2024-01-01T00:00:00",
    )
    return EmbeddedFile(file_meta=meta, raw_text=identity, embedding=embedding, status="embedded")


def test_split_mixed_doctype_clusters_without_reclustering():
    agent = ClusteringAgent.__new__(ClusteringAgent)
    files = [
        _embedded("resume1.txt", "resume: software developer python projects", [1.0, 0.0]),
        _embedded("resume2.txt", "resume: data analyst sql dashboards", [0.9, 0.1]),
        _embedded("plan1.txt", "agreement: health plan coverage deductible", [0.1, 0.9]),
        _embedded("plan2.txt", "agreement: student insurance policy benefits", [0.0, 1.0]),
    ]
    labels = agent._split_mixed_doctype_clusters(files, np.array([0, 0, 0, 0]))
    assert len(set(labels)) == 2
    assert labels[0] == labels[1]
    assert labels[2] == labels[3]
    assert labels[0] != labels[2]
