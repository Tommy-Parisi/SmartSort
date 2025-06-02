import numpy as np
from sklearn.cluster import AgglomerativeClustering
from core.models import EmbeddedFile, ClusteredFile
from core.utils import log_error

class ClusteringAgent:
    def __init__(self, max_clusters=8):
        self.max_clusters = max_clusters

    def _calculate_n_clusters(self, n_files: int) -> int:
        """Calculate the optimal number of clusters based on the number of files."""
        return min(self.max_clusters, max(2, n_files // 5))

    def cluster(self, embedded_files: list[EmbeddedFile]) -> list[ClusteredFile]:
        valid_files = [f for f in embedded_files if f.status == "embedded" and f.embedding]

        if len(valid_files) < 2:
            log_error("[ClusteringAgent] Not enough embeddings to cluster.")
            return []

        X = np.array([f.embedding for f in valid_files])
        try:
            n_clusters = self._calculate_n_clusters(len(valid_files))
            model = AgglomerativeClustering(
                n_clusters=n_clusters,
                metric='cosine',
                linkage='average'
            )
            labels = model.fit_predict(X)
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