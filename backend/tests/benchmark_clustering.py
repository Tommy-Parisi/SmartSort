"""
Benchmark extraction quality and clustering performance.

Usage (from repo root):
    python -m backend.tests.benchmark_clustering [folder_path]

Prints per-file:
    - raw_tokens   : word count of full file (pre-fix baseline)
    - ext_tokens   : word count of identity string our extractor produces
    - compression  : raw / extracted ratio
    - ms           : extraction + embedding time

Then prints cluster-level:
    - silhouette score (cosine, non-noise files)
    - cluster count / noise count
"""

import sys
import time
import argparse
from pathlib import Path
from collections import defaultdict

# Allow running as a script from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np

from backend.agents.ingestion_manager import IngestionManager
from backend.agents.extractor_router import ExtractorRouter
from backend.agents.embedding_agent import EmbeddingAgent
from backend.agents.clustering_agent import ClusteringAgent


def _word_count(text: str) -> int:
    return len(text.split())


def _raw_word_count(file_path: str) -> int:
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            return _word_count(f.read())
    except Exception:
        return 0


def run_benchmark(folder_path: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  SmartSort Extraction Benchmark")
    print(f"  Folder: {folder_path}")
    print(f"{'=' * 70}\n")

    ingestor = IngestionManager(folder_path)
    ingestor.scan()

    if not ingestor.file_meta_queue:
        print("No files found.")
        return

    print(f"Files found: {len(ingestor.file_meta_queue)}\n")

    router = ExtractorRouter()
    embedder = EmbeddingAgent()

    col = "{:<42} {:<10} {:>9} {:>9} {:>8} {:>6}"
    print(col.format("File", "Type", "RawTok", "ExtTok", "Compr", "ms"))
    print("-" * 88)

    file_stats = []
    embedded_files = []
    total_ms = 0.0

    for fmeta in ingestor.file_meta_queue:
        raw_tok = _raw_word_count(fmeta.file_path)

        t0 = time.perf_counter()
        content = router.route(fmeta)
        t1 = time.perf_counter()
        embedded = embedder.embed(content)
        t2 = time.perf_counter()

        ms = (t2 - t0) * 1000
        total_ms += ms

        ext_tok = _word_count(content.raw_text)
        compression = raw_tok / max(ext_tok, 1)

        print(col.format(
            fmeta.file_name[:41],
            fmeta.detected_type[:9],
            f"{raw_tok:,}",
            f"{ext_tok:,}",
            f"{compression:.1f}x",
            f"{ms:.0f}",
        ))

        file_stats.append({
            "raw_tok": raw_tok,
            "ext_tok": ext_tok,
            "compression": compression,
            "ms": ms,
            "status": content.status,
        })
        embedded_files.append(embedded)

    print("-" * 88)

    valid = [s for s in file_stats if s["status"] == "success"]
    if valid:
        avg_raw = sum(s["raw_tok"] for s in valid) / len(valid)
        avg_ext = sum(s["ext_tok"] for s in valid) / len(valid)
        avg_comp = sum(s["compression"] for s in valid) / len(valid)
        avg_ms = total_ms / len(file_stats)
        print(f"\nAverages — raw: {avg_raw:.0f} tok | extracted: {avg_ext:.0f} tok "
              f"| compression: {avg_comp:.1f}x | {avg_ms:.0f} ms/file")

    # ── Clustering ────────────────────────────────────────────────────────────
    valid_emb = [e for e in embedded_files if e.status == "embedded" and e.embedding]
    print(f"\n{'=' * 70}")
    print(f"  Clustering ({len(valid_emb)} embeddable files)")
    print(f"{'=' * 70}\n")

    if len(valid_emb) < 3:
        print("Not enough embeddings to cluster (need ≥ 3).")
        return

    t_clust = time.perf_counter()
    clusterer = ClusteringAgent(min_cluster_size=2)
    clustered = clusterer.cluster(valid_emb)
    t_clust = time.perf_counter() - t_clust

    if not clustered:
        print("Clustering returned no results.")
        return

    labels = np.array([f.cluster_id for f in clustered])
    n_clusters = len(set(labels) - {-1})
    noise_count = int((labels == -1).sum())

    print(f"Clusters: {n_clusters}   Noise: {noise_count}   Time: {t_clust:.1f}s\n")

    try:
        from sklearn.metrics import silhouette_score
        X = np.array([f.embedding for f in clustered])
        mask = labels != -1
        if mask.sum() > 1 and len(set(labels[mask])) > 1:
            score = silhouette_score(X[mask], labels[mask], metric="cosine")
            print(f"Silhouette score (cosine, non-noise): {score:.4f}")
            if score > 0.5:
                print("  → Excellent separation")
            elif score > 0.25:
                print("  → Reasonable separation")
            else:
                print("  → Weak separation — consider tuning min_cluster_size or threshold")
        else:
            print("Not enough non-noise samples for silhouette score.")
    except Exception as e:
        print(f"Silhouette score unavailable: {e}")

    cluster_map: dict = defaultdict(list)
    for f in clustered:
        cluster_map[f.cluster_id].append(f)

    print("\nCluster breakdown:")
    for cid in sorted(cluster_map):
        label = "NOISE" if cid == -1 else f"Cluster {cid:2d}"
        files = cluster_map[cid]
        names = ", ".join(f.file_meta.file_name for f in files[:4])
        suffix = f" + {len(files) - 4} more" if len(files) > 4 else ""
        print(f"  {label} ({len(files):3d} files)  {names}{suffix}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark SmartSort extraction + clustering")
    parser.add_argument(
        "folder",
        nargs="?",
        default="backend/tests/mixed_inputs",
        help="Folder to benchmark (default: backend/tests/mixed_inputs)",
    )
    args = parser.parse_args()
    run_benchmark(args.folder)
