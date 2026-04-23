import sys
from collections import defaultdict

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import calinski_harabasz_score
from sklearn.metrics.pairwise import cosine_distances

from ..core.models import EmbeddedFile, ClusteredFile
from ..core.utils import log_error
from .identity_utils import extract_prefixed_doctype

class SemanticClusterer:
    def __init__(self, fallback_k_range=(2, 10), min_cluster_size=3):
        self.fallback_k_range = fallback_k_range
        self.min_cluster_size = min_cluster_size

    def cluster(self, X: np.ndarray) -> np.ndarray:
        print("Trying HDBSCAN clustering...", file=sys.stderr)
        try:
            # Precompute cosine distance matrix
            distance_matrix = cosine_distances(X)

            import hdbscan
            hdb = hdbscan.HDBSCAN(metric='precomputed', min_cluster_size=self.min_cluster_size)
            labels = hdb.fit_predict(distance_matrix)

            n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
            print(f"  HDBSCAN found {n_clusters} clusters", file=sys.stderr)

            if n_clusters >= 2:
                return labels
            else:
                print("  HDBSCAN found fewer than 2 clusters. Falling back to Agglomerative clustering.", file=sys.stderr)
        except Exception as e:
            print(f"  HDBSCAN failed: {e}", file=sys.stderr)
            log_error(f"[SemanticClusterer] HDBSCAN failed: {e}")

        return self._fallback_agglomerative(X)


    def _fallback_agglomerative(self, X: np.ndarray) -> np.ndarray:
        best_score = -1
        best_k = None
        best_labels = None

        print(f"Testing fallback cluster counts from {self.fallback_k_range[0]} to {min(self.fallback_k_range[1], len(X))}", file=sys.stderr)

        for k in range(self.fallback_k_range[0], min(self.fallback_k_range[1], len(X)) + 1):
            try:
                model = AgglomerativeClustering(n_clusters=k, metric='cosine', linkage='average')
                labels = model.fit_predict(X)

                if len(set(labels)) == 1:
                    print(f"  Skipped k={k} (only one cluster)", file=sys.stderr)
                    continue

                score = calinski_harabasz_score(X, labels)
                print(f"  k={k} → Calinski-Harabasz Score: {score:.2f}", file=sys.stderr)

                if score > best_score:
                    best_score = score
                    best_k = k
                    best_labels = labels
            except Exception as e:
                print(f"  Error for k={k}: {e}", file=sys.stderr)
                log_error(f"[SemanticClusterer] Agglomerative error for k={k}: {e}")

        if best_labels is None:
            raise ValueError("Could not determine optimal clustering with fallback.")

        print(f"Best k selected: {best_k} with Calinski-Harabasz score {best_score:.2f}", file=sys.stderr)
        return best_labels


class ClusteringAgent:
    def __init__(self, fallback_k_range=(2, 10), min_cluster_size=3):
        from sentence_transformers import SentenceTransformer
        self.name_embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.clusterer = SemanticClusterer(
            fallback_k_range=fallback_k_range,
            min_cluster_size=min_cluster_size
        )

    def cluster(self, embedded_files: list[EmbeddedFile]) -> list[ClusteredFile]:
        valid_files = [f for f in embedded_files if f.status == "embedded" and f.embedding]

        if len(valid_files) < 2:
            log_error("[ClusteringAgent] Not enough embeddings to cluster.")
            return []

        X = np.array([f.embedding for f in valid_files])
        try:
            labels = self.clusterer.cluster(X)
            labels = self._split_mixed_doctype_clusters(valid_files, labels)
        except Exception as e:
            log_error(f"[ClusteringAgent] Clustering failed: {e}")
            return []

        clustered = []
        for file, label in zip(valid_files, labels):
            clustered.append(ClusteredFile(
                file_meta=file.file_meta,
                embedding=file.embedding,
                raw_text=file.raw_text,
                cluster_id=int(label),
                status="clustered"
            ))

        return clustered

    def _split_mixed_doctype_clusters(
        self,
        embedded_files: list[EmbeddedFile],
        labels: np.ndarray
    ) -> np.ndarray:
        next_label = int(labels.max()) + 1 if len(labels) else 0
        refined = labels.copy()

        for cluster_id in sorted(set(int(label) for label in labels if int(label) != -1)):
            indices = [i for i, label in enumerate(labels) if int(label) == cluster_id]
            doctypes = [extract_prefixed_doctype(embedded_files[i].raw_text) for i in indices]
            typed_groups: dict[str, list[int]] = defaultdict(list)
            unknown_indices: list[int] = []

            for idx, doctype in zip(indices, doctypes):
                if doctype:
                    typed_groups[doctype].append(idx)
                else:
                    unknown_indices.append(idx)

            if len(typed_groups) <= 1:
                continue

            dominant_doctype = max(typed_groups.items(), key=lambda item: len(item[1]))[0]
            for idx in unknown_indices:
                typed_groups[dominant_doctype].append(idx)

            first = True
            for _, group_indices in sorted(typed_groups.items(), key=lambda item: item[0]):
                if first:
                    for idx in group_indices:
                        refined[idx] = cluster_id
                    first = False
                else:
                    for idx in group_indices:
                        refined[idx] = next_label
                    next_label += 1

        return refined

    def merge_similar_clusters(
        self,
        cluster_map: dict[int, list[ClusteredFile]],
        cluster_names: dict[int, str],
        similarity_threshold: float = 0.75
        ) -> dict[int, list[ClusteredFile]]:
        sorted_ids = sorted(cluster_names.keys())
        folder_names = [cluster_names[i] for i in sorted_ids]
        embeddings = self.name_embedder.encode(folder_names, convert_to_tensor=True)

        from sentence_transformers import util
        similarity_matrix = util.pytorch_cos_sim(embeddings, embeddings).cpu().numpy()

        parent = {i: i for i in range(len(sorted_ids))}

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i, j):
            pi, pj = find(i), find(j)
            if pi != pj:
                parent[pj] = pi

        for i in range(len(sorted_ids)):
            for j in range(i + 1, len(sorted_ids)):
                if similarity_matrix[i][j] >= similarity_threshold:
                    union(i, j)

        group_to_cluster_ids = defaultdict(list)
        for i, cluster_id in enumerate(sorted_ids):
            group_id = find(i)
            group_to_cluster_ids[group_id].append(cluster_id)

        merged_cluster_map = {}
        new_cluster_id = 0
        for cluster_ids in group_to_cluster_ids.values():
            merged_files = []
            for cid in cluster_ids:
                merged_files.extend(cluster_map.get(cid, []))
            merged_cluster_map[new_cluster_id] = merged_files
            new_cluster_id += 1

        return merged_cluster_map
