from backend.agents.ingestion_manager import IngestionManager
from backend.agents.extractor_router import ExtractorRouter
from backend.agents.embedding_agent import EmbeddingAgent
from backend.agents.clustering_agent import ClusteringAgent
from backend.agents.folder_naming_agent import FolderNamingAgent
from core.models import FileContent
from collections import defaultdict
from backend.agents.file_relocation_agent import FileRelocationAgent
from dotenv import load_dotenv
import random
load_dotenv()


def _stratified_sample(file_metas, max_files: int, seed: int = 42):
    """Random stratified sample by detected_type, preserving type distribution."""
    if len(file_metas) <= max_files:
        return file_metas
    rng = random.Random(seed)
    by_type = defaultdict(list)
    for fm in file_metas:
        by_type[fm.detected_type].append(fm)
    total = len(file_metas)
    result = []
    for files in by_type.values():
        n = max(1, round(len(files) / total * max_files))
        n = min(n, len(files))
        result.extend(rng.sample(files, n))
    if len(result) > max_files:
        result = rng.sample(result, max_files)
    return result


def run_pipeline(input_folder: str, debug_preview: bool = True, max_files: int = None):
    print(f"\n Starting pipeline on: {input_folder}\n")

    # 1. Ingestion
    ingestor = IngestionManager(input_folder)
    ingestor.scan()

    if not ingestor.file_meta_queue:
        print("  No files found. Check your folder path or filters.")
        return

    if max_files is not None and len(ingestor.file_meta_queue) > max_files:
        ingestor.file_meta_queue = _stratified_sample(ingestor.file_meta_queue, max_files)
        print(f" Sampled {len(ingestor.file_meta_queue)} files (stratified, max={max_files}).\n")
    else:
        print(f" Ingested {len(ingestor.file_meta_queue)} files.\n")

    # 2. Extraction
    router = ExtractorRouter()
    extracted = []

    for fmeta in ingestor.file_meta_queue:
        content: FileContent = router.route(fmeta)
        extracted.append(content)

        status_icon = "GOOD" if content.status == "success" else "FAIL"
        print(f"{status_icon} {fmeta.file_name} → {content.status}")

        if debug_preview and content.status == "success":
            print("----- Extracted Preview -----")
            print(content.raw_text[:500].strip())  # First 500 chars
            print("-----------------------------\n")

    success_count = sum(1 for f in extracted if f.status == "success")
    fail_count = len(extracted) - success_count

    print(f"\n Extraction complete: {success_count} success, {fail_count} failed\n")

    # 3. Embedding
    embedder = EmbeddingAgent()
    embedded = []

    for extracted_file in extracted:
        embedded_file = embedder.embed(extracted_file)
        embedded.append(embedded_file)

    print(f"\nEmbedded {len([e for e in embedded if e.status == 'embedded'])} documents successfully.")

    # Print a few example embeddings
    print("\n--- Sample Embeddings ---")

    for embedded_file in embedded[:25]:  # Show first 5 for sanity
        if embedded_file.status == "embedded":
            print(f"{embedded_file.file_meta.file_name}")
            print(f"Embedding (first 5 values): {embedded_file.embedding[:5]}")
            print(f"Vector length: {len(embedded_file.embedding)}\n")

    # 4. Clustering
    print("\n--- Clustering Phase ---")
    clusterer = ClusteringAgent(fallback_k_range=(2, 10), min_cluster_size=2)
    print("Clustering with HDBSCAN (fallback to Agglomerative if needed)...")

    clustered = clusterer.cluster(embedded)

    if clustered:
        n_clusters = len(set(f.cluster_id for f in clustered))
        print(f"\nClustering complete: selected {n_clusters} clusters.\n")

        cluster_map = defaultdict(list)
        for f in clustered:
            cluster_map[f.cluster_id].append(f)

        # Log each cluster and its members
        print("\n--- Cluster Breakdown ---")
        for cluster_id, files in sorted(cluster_map.items()):
            print(f"\nCluster {cluster_id} ({len(files)} file{'s' if len(files) != 1 else ''}):")
            for f in files:
                print(f"  - {f.file_meta.file_name}")


    # 5. Folder Naming
    naming_agent = FolderNamingAgent()
    folder_names = naming_agent.name_clusters(cluster_map)
    print("\n--- Initial Cluster Labels ---")
    for cluster_id, files in sorted(cluster_map.items()):
        label = folder_names.get(cluster_id, f"cluster_{cluster_id}")
        print(f"\n{label} (Cluster {cluster_id}) — {len(files)} file{'s' if len(files) != 1 else ''}")
        for f in files:
            print(f"  - {f.file_meta.file_name}")

    # 5.1 Merging Similar Clusters
    print("\n--- Merging Similar Clusters ---")
    cluster_map = clusterer.merge_similar_clusters(cluster_map, folder_names)
    folder_names = naming_agent.name_clusters(cluster_map)


    print("\n--- Final Cluster Labels ---")
    for cluster_id, files in sorted(cluster_map.items()):
        label = folder_names.get(cluster_id, f"cluster_{cluster_id}")
        print(f"\n{label} (Cluster {cluster_id}) — {len(files)} file{'s' if len(files) != 1 else ''}")
        for f in files:
            print(f"  - {f.file_meta.file_name}")  

    # 6. File Relocation
    relocation_agent = FileRelocationAgent(base_destination_dir=input_folder, dry_run=False)
    relocation_results = relocation_agent.relocate_files(cluster_map)
    print("\n--- File Relocation Results ---")

    # 7. Persist faiss index for incremental assignment
    try:
        import numpy as np
        from backend.agents.index_manager import save_index
        from pathlib import Path as _Path

        embeddings_list, labels_list, new_paths, cluster_folders = [], [], [], {}
        for cid, files in cluster_map.items():
            if cid == -1:
                continue
            fname = folder_names.get(cid, f"cluster_{cid}")
            folder_abs = str(_Path(input_folder) / fname)
            cluster_folders[cid] = folder_abs
            for f in files:
                if not f.embedding:
                    continue
                embeddings_list.append(f.embedding)
                labels_list.append(cid)
                new_paths.append(str(_Path(folder_abs) / _Path(f.file_meta.file_path).name))

        if embeddings_list:
            save_index(
                np.array(embeddings_list, dtype=np.float32),
                np.array(labels_list),
                new_paths,
                cluster_folders,
            )
            print("Incremental assignment index saved.")
    except Exception as e:
        print(f"Index persistence failed (non-fatal): {e}")

    print("\nPipeline completed successfully!\n")



