"""
Persistent faiss index for incremental file assignment.

Files written to SMARTSORT_DIR (default ~/.smartsort/):
  index.faiss          -- IndexFlatIP of L2-normalised embeddings (cosine via IP)
  index_meta.json      -- [{cluster_id, file_path}, ...] indexed by faiss row
  centroids.pkl        -- {cluster_id: np.ndarray} normalised mean per cluster
  cluster_folders.json -- {cluster_id: abs_folder_path}
"""

import json
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

SMARTSORT_DIR = Path.home() / ".smartsort"


def _dir(override: Optional[Path] = None) -> Path:
    d = override or SMARTSORT_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def normalize(vectors: np.ndarray) -> np.ndarray:
    """L2-normalise row vectors in-place safe copy."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return vectors / norms


def save_index(
    embeddings: np.ndarray,
    labels: np.ndarray,
    file_paths: List[str],
    cluster_folders: Dict[int, str],
    output_dir: Optional[Path] = None,
) -> None:
    """
    Persist a faiss index + metadata from a completed clustering run.

    Args:
        embeddings:      (N, D) float32 array — one row per file
        labels:          (N,) int array — cluster label per file (-1 = noise)
        file_paths:      list of absolute file paths, one per row
        cluster_folders: {cluster_id: absolute folder path}
        output_dir:      override for ~/.smartsort/ (useful in tests)
    """
    try:
        import faiss
    except ImportError:
        print("[IndexManager] faiss-cpu not installed — skipping index persistence.")
        return

    d = _dir(output_dir)
    X = embeddings.astype(np.float32)
    normed = normalize(X.copy())

    # faiss index
    index = faiss.IndexFlatIP(normed.shape[1])
    index.add(normed)
    faiss.write_index(index, str(d / "index.faiss"))

    # per-row metadata
    meta = [
        {"cluster_id": int(labels[i]), "file_path": file_paths[i]}
        for i in range(len(labels))
    ]
    with open(d / "index_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    # per-cluster normalised centroids
    centroids: Dict[int, List[float]] = {}
    for cid in set(int(l) for l in labels):
        if cid == -1:
            continue
        mask = labels == cid
        centroid = normed[mask].mean(axis=0)
        norm = float(np.linalg.norm(centroid))
        centroids[cid] = (centroid / norm if norm > 0 else centroid).tolist()
    with open(d / "centroids.pkl", "wb") as f:
        pickle.dump(centroids, f)

    # cluster folder map (string keys for JSON)
    with open(d / "cluster_folders.json", "w") as f:
        json.dump({str(k): v for k, v in cluster_folders.items()}, f, indent=2)

    n_clusters = len(centroids)
    print(f"[IndexManager] Saved {len(X)} vectors, {n_clusters} clusters → {d}")


def load_index(
    index_dir: Optional[Path] = None,
) -> Tuple:
    """
    Load faiss index + metadata from disk.

    Returns:
        (faiss_index, index_meta, centroids, cluster_folders)

    Raises:
        FileNotFoundError if the index has not been built yet.
        ImportError if faiss-cpu is not installed.
    """
    try:
        import faiss
    except ImportError:
        raise ImportError("faiss-cpu is not installed. Run: pip install faiss-cpu")

    d = index_dir or SMARTSORT_DIR
    index = faiss.read_index(str(d / "index.faiss"))

    with open(d / "index_meta.json") as f:
        index_meta: List[Dict] = json.load(f)

    with open(d / "centroids.pkl", "rb") as f:
        centroids: Dict[int, np.ndarray] = pickle.load(f)

    with open(d / "cluster_folders.json") as f:
        raw = json.load(f)
    cluster_folders: Dict[int, str] = {int(k): v for k, v in raw.items()}

    return index, index_meta, centroids, cluster_folders


def append_to_index(
    embedding: np.ndarray,
    cluster_id: int,
    file_path: str,
    index_dir: Optional[Path] = None,
) -> None:
    """Add a newly-assigned file to the persistent index without rebuilding it."""
    try:
        import faiss
    except ImportError:
        return

    d = index_dir or SMARTSORT_DIR
    idx_path = d / "index.faiss"
    meta_path = d / "index_meta.json"

    if not idx_path.exists():
        return

    index = faiss.read_index(str(idx_path))
    vec = normalize(embedding.reshape(1, -1).astype(np.float32))
    index.add(vec)
    faiss.write_index(index, str(idx_path))

    try:
        with open(meta_path) as f:
            meta = json.load(f)
    except Exception:
        meta = []

    meta.append({"cluster_id": cluster_id, "file_path": file_path})
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)


def index_exists(index_dir: Optional[Path] = None) -> bool:
    d = index_dir or SMARTSORT_DIR
    return (d / "index.faiss").exists()
