"""
Tests for AssignmentAgent and IndexManager.

Strategy: build a real faiss index with well-separated cluster centres,
then call _query_index() directly with known vectors.  This avoids loading
the sentence-transformer model (slow) while still exercising the actual
similarity / majority-vote logic.
"""

import json
import pickle
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────

DIM = 384
N_CLUSTERS = 3
N_PER_CLUSTER = 4
RNG = np.random.default_rng(42)


def _unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def _make_centres() -> np.ndarray:
    """Create well-separated unit vectors in R^DIM."""
    centres = RNG.standard_normal((N_CLUSTERS, DIM)).astype(np.float32)
    return np.array([_unit(c) for c in centres])


@pytest.fixture(scope="module")
def index_dir():
    """
    Build a temporary faiss index with 3 clusters × 4 files each
    and yield the directory path.
    """
    import faiss
    from backend.agents.index_manager import save_index

    tmp = Path(tempfile.mkdtemp(prefix="smartsort_idx_test_"))
    centres = _make_centres()

    embeddings, labels, file_paths, cluster_folders = [], [], [], {}

    for cid in range(N_CLUSTERS):
        folder = tmp / f"cluster_{cid}"
        folder.mkdir()
        cluster_folders[cid] = str(folder)

        for j in range(N_PER_CLUSTER):
            noise = RNG.standard_normal(DIM).astype(np.float32) * 0.05
            vec = _unit(centres[cid] + noise)
            embeddings.append(vec)
            labels.append(cid)
            fp = folder / f"file_{cid}_{j}.txt"
            fp.write_text(f"content {cid} {j}")
            file_paths.append(str(fp))

    save_index(
        np.array(embeddings, dtype=np.float32),
        np.array(labels),
        file_paths,
        cluster_folders,
        output_dir=tmp,
    )

    yield tmp, centres, cluster_folders
    shutil.rmtree(tmp)


@pytest.fixture(scope="module")
def agent(index_dir):
    """AssignmentAgent with its index pre-loaded from the test dir."""
    from backend.agents.assignment_agent import AssignmentAgent

    tmp, _, _ = index_dir
    # Bypass the real model — we test _query_index directly in most tests.
    a = AssignmentAgent.__new__(AssignmentAgent)
    a.threshold = 0.65
    a.k = 5
    a.index_dir = tmp
    a.extractor = None   # not used in _query_index tests
    a.embedder = None    # not used in _query_index tests
    a.index = None
    a.index_meta = []
    a.centroids = {}
    a.cluster_folders = {}
    a._load_index()
    return a


# ── index_manager tests ───────────────────────────────────────────────────────

def test_save_and_load_index(index_dir):
    from backend.agents.index_manager import load_index, index_exists

    tmp, _, cluster_folders = index_dir
    assert index_exists(tmp)

    index, meta, centroids, folders = load_index(tmp)
    assert index.ntotal == N_CLUSTERS * N_PER_CLUSTER
    assert len(meta) == N_CLUSTERS * N_PER_CLUSTER
    assert len(centroids) == N_CLUSTERS
    assert len(folders) == N_CLUSTERS
    assert set(folders.values()) == set(cluster_folders.values())


def test_index_meta_has_correct_cluster_ids(index_dir):
    from backend.agents.index_manager import load_index

    tmp, _, _ = index_dir
    _, meta, _, _ = load_index(tmp)
    cluster_ids = {e["cluster_id"] for e in meta}
    assert cluster_ids == set(range(N_CLUSTERS))


def test_centroids_are_unit_vectors(index_dir):
    from backend.agents.index_manager import load_index

    tmp, _, _ = index_dir
    _, _, centroids, _ = load_index(tmp)
    for cid, c in centroids.items():
        arr = np.array(c)
        assert abs(np.linalg.norm(arr) - 1.0) < 1e-5, f"Centroid {cid} not unit-length"


def test_append_to_index(index_dir):
    from backend.agents.index_manager import load_index, append_to_index

    tmp, centres, _ = index_dir
    index_before, _, _, _ = load_index(tmp)
    total_before = index_before.ntotal

    new_vec = _unit(centres[0] + RNG.standard_normal(DIM).astype(np.float32) * 0.05)
    append_to_index(new_vec, cluster_id=0, file_path="/tmp/new_file.txt", index_dir=tmp)

    index_after, meta_after, _, _ = load_index(tmp)
    assert index_after.ntotal == total_before + 1
    assert meta_after[-1]["cluster_id"] == 0
    assert meta_after[-1]["file_path"] == "/tmp/new_file.txt"


# ── AssignmentAgent._query_index tests ───────────────────────────────────────

def test_query_assigns_near_cluster(agent, index_dir):
    """A vector close to cluster 0's centre should be assigned to cluster 0."""
    _, centres, _ = index_dir
    test_vec = _unit(centres[0] + RNG.standard_normal(DIM).astype(np.float32) * 0.02)
    result = agent._query_index(test_vec.reshape(1, -1))

    assert result is not None
    assert result.cluster_id == 0
    assert result.similarity > 0  # mean of k-neighbours can be slightly below top-1 gate


def test_query_correct_majority_vote(agent, index_dir):
    """Vectors near each centre should each map to their respective cluster."""
    _, centres, _ = index_dir
    for cid in range(N_CLUSTERS):
        vec = _unit(centres[cid] + RNG.standard_normal(DIM).astype(np.float32) * 0.02)
        result = agent._query_index(vec.reshape(1, -1))
        assert result is not None, f"No result for cluster {cid}"
        assert result.cluster_id == cid, (
            f"Expected cluster {cid}, got {result.cluster_id}"
        )


def test_query_below_threshold_returns_none(agent):
    """A random vector with low similarity to everything should return None."""
    # Force low similarity by using an agent with an impossibly high threshold
    from backend.agents.assignment_agent import AssignmentAgent
    high_threshold_agent = AssignmentAgent.__new__(AssignmentAgent)
    high_threshold_agent.threshold = 0.9999
    high_threshold_agent.k = 5
    high_threshold_agent.index = agent.index
    high_threshold_agent.index_meta = agent.index_meta
    high_threshold_agent.cluster_folders = agent.cluster_folders

    random_vec = _unit(RNG.standard_normal(DIM).astype(np.float32))
    result = high_threshold_agent._query_index(random_vec.reshape(1, -1))
    assert result is None


def test_query_returns_folder_path(agent, index_dir):
    """Result should carry the correct folder path for the winning cluster."""
    _, centres, cluster_folders = index_dir
    vec = _unit(centres[1] + RNG.standard_normal(DIM).astype(np.float32) * 0.02)
    result = agent._query_index(vec.reshape(1, -1))

    assert result is not None
    assert result.folder_path == cluster_folders[1]


def test_query_neighbor_votes_positive(agent, index_dir):
    """neighbor_votes should be between 1 and k."""
    _, centres, _ = index_dir
    vec = _unit(centres[2] + RNG.standard_normal(DIM).astype(np.float32) * 0.02)
    result = agent._query_index(vec.reshape(1, -1))

    assert result is not None
    assert 1 <= result.neighbor_votes <= agent.k


def test_no_index_returns_none():
    """AssignmentAgent with no index should return None gracefully."""
    from backend.agents.assignment_agent import AssignmentAgent

    tmp = Path(tempfile.mkdtemp(prefix="smartsort_empty_"))
    try:
        a = AssignmentAgent.__new__(AssignmentAgent)
        a.threshold = 0.65
        a.k = 5
        a.index_dir = tmp
        a.extractor = None
        a.embedder = None
        a.index = None
        a.index_meta = []
        a.cluster_folders = {}
        a._load_index()

        # No index built — _query_index on a None index should return None
        assert a._query_index(np.zeros((1, DIM), dtype=np.float32)) is None
    finally:
        shutil.rmtree(tmp)
