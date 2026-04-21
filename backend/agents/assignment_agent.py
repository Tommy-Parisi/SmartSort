"""
Incremental file assignment against an existing faiss cluster index.

Pipeline per new file:
  1. Extract identity string via ExtractorRouter
  2. Embed via EmbeddingAgent (model stays resident — don't reload)
  3. L2-normalise → query faiss IndexFlatIP for k=5 nearest neighbours
  4. Gate on top-1 cosine similarity vs threshold
  5. Majority-vote the k neighbours' cluster labels
  6. Return AssignmentResult (cluster_id + folder path) or None

None means the file goes to the unassigned queue; the caller triggers a
re-cluster when the queue fills up.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from ..core.constants import FILE_TYPE_MAP
from ..core.models import FileMeta
from ..agents.extractor_router import ExtractorRouter
from ..agents.embedding_agent import EmbeddingAgent
from ..agents.index_manager import load_index, append_to_index, index_exists, normalize, SMARTSORT_DIR


@dataclass
class AssignmentResult:
    cluster_id: int
    folder_path: str    # absolute destination folder
    similarity: float   # mean cosine sim of k neighbours in winning cluster
    neighbor_votes: int # how many of the k neighbours voted for this cluster


class AssignmentAgent:
    """
    Loads the faiss index once and handles incremental assignment.
    Designed to stay resident in the daemon process.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        threshold: float = 0.65,
        k_neighbours: int = 5,
        index_dir: Optional[Path] = None,
    ):
        self.threshold = threshold
        self.k = k_neighbours
        self.index_dir = Path(index_dir) if index_dir else SMARTSORT_DIR

        # These stay loaded for the lifetime of the daemon
        self.extractor = ExtractorRouter()
        self.embedder = EmbeddingAgent(model_name)

        # faiss state — populated by _load_index()
        self.index = None
        self.index_meta: List[Dict] = []
        self.centroids: Dict[int, np.ndarray] = {}
        self.cluster_folders: Dict[int, str] = {}

        self._load_index()

    # ── Public API ────────────────────────────────────────────────────────────

    def assign(self, file_path: str) -> Optional[AssignmentResult]:
        """
        Attempt to assign a file to an existing cluster.

        Returns AssignmentResult if similarity > threshold, else None.
        """
        if self.index is None or self.index.ntotal == 0:
            return None

        p = Path(file_path)
        if not p.exists():
            return None

        ext = p.suffix.lower()
        fmeta = FileMeta(
            file_path=str(p),
            file_name=p.name,
            extension=ext,
            detected_type=FILE_TYPE_MAP.get(ext, "unknown"),
            size_kb=round(p.stat().st_size / 1024, 2),
            created_at=datetime.fromtimestamp(p.stat().st_ctime).isoformat(),
            modified_at=datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
            status="pending",
        )

        content = self.extractor.route(fmeta)
        if content.status != "success":
            return None

        embedded = self.embedder.embed(content)
        if embedded.status != "embedded" or not embedded.embedding:
            return None

        vec = normalize(np.array(embedded.embedding, dtype=np.float32).reshape(1, -1))
        result = self._query_index(vec)

        if result is not None:
            # Persist to disk, then mirror the change in-memory without a full reload.
            append_to_index(vec.squeeze(), result.cluster_id, str(p), self.index_dir)
            if self.index is not None:
                self.index.add(vec)
                self.index_meta.append({"cluster_id": result.cluster_id, "file_path": str(p)})

        return result

    def reload_index(self) -> None:
        """Reload from disk — call this after a full re-cluster."""
        self._load_index()

    # ── Index query (also used directly in tests) ─────────────────────────────

    def _query_index(self, normed_vec: np.ndarray) -> Optional[AssignmentResult]:
        """
        Query the faiss index with a pre-normalised (1, D) float32 vector.
        Returns AssignmentResult or None.
        """
        if self.index is None:
            return None
        k = min(self.k, self.index.ntotal)
        if k == 0:
            return None

        similarities, faiss_indices = self.index.search(normed_vec, k)
        top_sim = float(similarities[0][0])

        if top_sim < self.threshold:
            return None

        # Majority vote: group k neighbours by cluster_id
        votes: Dict[int, List[float]] = {}
        for sim, idx in zip(similarities[0], faiss_indices[0]):
            if idx == -1:
                continue
            cid = self.index_meta[idx]["cluster_id"]
            if cid == -1:   # noise label — skip
                continue
            votes.setdefault(cid, []).append(float(sim))

        if not votes:
            return None

        # Winning cluster: most votes, ties broken by total similarity
        winning_cid = max(votes, key=lambda c: (len(votes[c]), sum(votes[c])))
        mean_sim = sum(votes[winning_cid]) / len(votes[winning_cid])
        folder_path = self.cluster_folders.get(winning_cid, "")

        return AssignmentResult(
            cluster_id=winning_cid,
            folder_path=folder_path,
            similarity=mean_sim,
            neighbor_votes=len(votes[winning_cid]),
        )

    # ── Internals ─────────────────────────────────────────────────────────────

    def _load_index(self) -> None:
        if not index_exists(self.index_dir):
            return
        try:
            self.index, self.index_meta, self.centroids, self.cluster_folders = (
                load_index(self.index_dir)
            )
        except Exception as e:
            print(f"[AssignmentAgent] Could not load index: {e}")
