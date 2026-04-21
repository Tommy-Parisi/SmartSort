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
import random
from pathlib import Path
from collections import defaultdict

# Allow running as a script from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np

from backend.agents.ingestion_manager import IngestionManager
from backend.agents.extractor_router import ExtractorRouter
from backend.agents.embedding_agent import EmbeddingAgent
from backend.agents.clustering_agent import ClusteringAgent
from backend.agents.folder_naming_agent import FolderNamingAgent


def _stratified_sample(file_metas, max_files: int, seed: int = 42):
    """Equal-per-type stratified sample — no single type can dominate the budget."""
    if len(file_metas) <= max_files:
        return file_metas
    rng = random.Random(seed)
    by_type = defaultdict(list)
    for fm in file_metas:
        by_type[fm.detected_type].append(fm)
    types = sorted(by_type.items(), key=lambda x: len(x[1]))
    result = []
    remaining = max_files
    for i, (_, files) in enumerate(types):
        types_left = len(types) - i
        n = min(remaining // types_left, len(files))
        result.extend(rng.sample(files, n))
        remaining -= n
    return result


def _word_count(text: str) -> int:
    return len(text.split())


def _raw_word_count(file_path: str) -> int:
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            return _word_count(f.read())
    except Exception:
        return 0


def run_benchmark(folder_path: str, max_files: int = None, show_all: bool = False) -> None:
    print(f"\n{'=' * 70}")
    print(f"  SmartSort Extraction Benchmark")
    print(f"  Folder: {folder_path}")
    print(f"{'=' * 70}\n")

    ingestor = IngestionManager(folder_path)
    ingestor.scan()

    if not ingestor.file_meta_queue:
        print("No files found.")
        return

    total_found = len(ingestor.file_meta_queue)
    if max_files is not None and total_found > max_files:
        ingestor.file_meta_queue = _stratified_sample(ingestor.file_meta_queue, max_files)
        print(f"Files found: {total_found}  →  sampled {len(ingestor.file_meta_queue)} (stratified, max={max_files})\n")
    else:
        print(f"Files found: {total_found}\n")

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
            "embed_status": embedded.status,
            "detected_type": fmeta.detected_type,
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

    # ── Embedding funnel by type ──────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print(f"  Embedding funnel by type")
    print(f"{'=' * 70}")
    by_type: dict = defaultdict(lambda: {"embedded": 0, "skipped": 0, "too_short": 0, "error": 0, "other": 0})
    for s in file_stats:
        bucket = s["embed_status"] if s["embed_status"] in ("embedded", "skipped", "too_short", "error") else "other"
        by_type[s["detected_type"]][bucket] += 1
    col_f = "{:<14} {:>8} {:>8} {:>10} {:>7}"
    print(col_f.format("Type", "embedded", "skipped", "too_short", "error"))
    print("-" * 52)
    for dtype, counts in sorted(by_type.items()):
        print(col_f.format(
            dtype[:13],
            counts["embedded"], counts["skipped"],
            counts["too_short"], counts["error"],
        ))
    total_emb = sum(s["embed_status"] == "embedded" for s in file_stats)
    total_skip = sum(s["embed_status"] == "skipped" for s in file_stats)
    total_short = sum(s["embed_status"] == "too_short" for s in file_stats)
    print("-" * 52)
    print(col_f.format("TOTAL", total_emb, total_skip, total_short,
                        sum(s["embed_status"] == "error" for s in file_stats)))

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

    # Top 20 non-noise clusters by size, then noise
    non_noise = [(cid, files) for cid, files in cluster_map.items() if cid != -1]
    non_noise.sort(key=lambda x: -len(x[1]))
    noise_files = cluster_map.get(-1, [])

    FLAG_THRESHOLD = 2
    flagged = []

    if show_all:
        # Full dump: every cluster, every file
        print(f"\n{'─' * 70}")
        for cid, files in non_noise:
            flag = " ⚑" if len(files) <= FLAG_THRESHOLD else ""
            if flag:
                flagged.append((cid, files))
            print(f"\n  Cluster #{cid}  ({len(files)} files){flag}")
            for f in files:
                print(f"    {f.file_meta.file_name}")
        if noise_files:
            print(f"\n  NOISE  ({len(noise_files)} files)")
            for f in noise_files:
                print(f"    {f.file_meta.file_name}")
        print(f"\n{'─' * 70}")
    else:
        col2 = "{:<12} {:>6}  {}"
        print(f"\n{'─' * 70}")
        print(col2.format("Cluster", "Files", "Sample filename"))
        print(f"{'─' * 70}")

        for cid, files in non_noise[:20]:
            sample = files[0].file_meta.file_name
            flag = " ⚑" if len(files) <= FLAG_THRESHOLD else ""
            if flag:
                flagged.append((cid, files))
            print(col2.format(f"  #{cid}", len(files), sample[:55]) + flag)

        if len(non_noise) > 20:
            print(f"  … {len(non_noise) - 20} more clusters not shown")

        if noise_files:
            sample = noise_files[0].file_meta.file_name
            print(col2.format("  NOISE", len(noise_files), sample[:55]))

        print(f"{'─' * 70}")

    if flagged:
        print(f"\n⚑  Flagged ({len(flagged)} cluster(s) with ≤{FLAG_THRESHOLD} files — possible noise leakage):")
        for cid, files in flagged:
            names = ", ".join(f.file_meta.file_name for f in files)
            print(f"   Cluster #{cid}: {names}")

    # ── TF-IDF folder naming ──────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print(f"  TF-IDF Folder Names (no API key)")
    print(f"{'=' * 70}")
    namer = FolderNamingAgent(use_llm_fallback=False)
    folder_names = namer.name_clusters(cluster_map)
    col3 = "{:<12} {:>6}  {}"
    print(col3.format("Cluster", "Files", "Proposed folder name"))
    print("-" * 55)
    for cid, files in non_noise:
        label = folder_names.get(cid, f"Cluster {cid}")
        print(col3.format(f"  #{cid}", len(files), label))
    print("-" * 55)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark SmartSort extraction + clustering")
    parser.add_argument(
        "folder",
        nargs="?",
        default="backend/tests/mixed_inputs",
        help="Folder to benchmark (default: backend/tests/mixed_inputs)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Cap files with stratified sampling across file types",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Print every cluster and every file in it",
    )
    args = parser.parse_args()
    run_benchmark(args.folder, max_files=args.max_files, show_all=args.show_all)
