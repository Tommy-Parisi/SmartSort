#!/usr/bin/env python3
"""
Tauri-compatible pipeline interface for the semantic file sorter.
Provides structured output and progress reporting for the frontend.
"""
import sys
import os
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict

# Add the backend directory to Python path for relative imports
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(backend_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import with proper paths
sys.path.insert(0, os.path.join(project_root, 'backend'))

from backend.agents.ingestion_manager import IngestionManager
from backend.agents.extractor_router import ExtractorRouter
from backend.agents.embedding_agent import EmbeddingAgent
from backend.agents.clustering_agent import ClusteringAgent
from backend.agents.folder_naming_agent import FolderNamingAgent
from backend.agents.file_relocation_agent import FileRelocationAgent
from backend.core.models import FileContent
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


class TauriPipeline:
    """Production-ready semantic file sorting pipeline for Tauri integration."""
    
    def __init__(self, input_folder: str):
        self.input_folder = Path(input_folder)
        self.results = {
            "status": "pending",
            "message": "",
            "progress": 0,
            "stages_completed": 0,
            "total_stages": 6,
            "files_processed": 0,
            "clusters_found": 0,
            "folders_created": [],
            "errors": [],
            "stats": {}
        }
    
    def log_progress(self, stage: int, message: str, progress: int = None):
        """Log progress for Tauri frontend consumption."""
        self.results["stages_completed"] = stage
        self.results["message"] = message
        if progress is not None:
            self.results["progress"] = progress
        
        # Send progress to stderr so it doesn't interfere with JSON output
        print(f"PROGRESS: {json.dumps(self.results)}", file=sys.stderr)
    
    def preview_clusters(self) -> Dict[str, Any]:
        """Quick preview to estimate number of clusters without full processing."""
        try:
            # 1. Quick Ingestion
            self.log_progress(1, "Scanning files...", 10)
            ingestor = IngestionManager(str(self.input_folder))
            ingestor.scan()
            
            if not ingestor.file_meta_queue:
                return {
                    "status": "success",
                    "estimated_clusters": 0,
                    "files_found": 0,
                    "message": "No files found in the specified folder."
                }
            
            files_count = len(ingestor.file_meta_queue)
            
            # Simple heuristic for cluster estimation
            if files_count <= 5:
                estimated_clusters = 1
            elif files_count <= 20:
                estimated_clusters = min(3, files_count // 3)
            elif files_count <= 50:
                estimated_clusters = min(5, files_count // 8)
            else:
                estimated_clusters = min(10, files_count // 10)
            
            return {
                "status": "success",
                "estimated_clusters": estimated_clusters,
                "files_found": files_count,
                "message": f"Found {files_count} files, estimated {estimated_clusters} semantic clusters."
            }
            
        except Exception as e:
            return {
                "status": "error",
                "estimated_clusters": 0,
                "files_found": 0,
                "message": f"Preview failed: {str(e)}"
            }
    
    def run_full_pipeline(self, dry_run: bool = False, max_files: int = None) -> Dict[str, Any]:
        """Run the complete semantic sorting pipeline."""
        try:
            # 1. Ingestion
            self.log_progress(1, "Scanning and ingesting files...", 5)
            ingestor = IngestionManager(str(self.input_folder))
            ingestor.scan()
            
            if not ingestor.file_meta_queue:
                self.results.update({
                    "status": "success",
                    "message": "No files found to process.",
                    "files_processed": 0
                })
                return self.results
            
            if max_files is not None and len(ingestor.file_meta_queue) > max_files:
                ingestor.file_meta_queue = _stratified_sample(ingestor.file_meta_queue, max_files)
                self.log_progress(1, f"Sampled {len(ingestor.file_meta_queue)} files (max={max_files})", 8)

            self.results["files_processed"] = len(ingestor.file_meta_queue)

            # 2. Extraction
            self.log_progress(2, "Extracting content from files...", 20)
            router = ExtractorRouter()
            extracted = []
            
            for i, fmeta in enumerate(ingestor.file_meta_queue):
                content: FileContent = router.route(fmeta)
                extracted.append(content)
                
                # Update progress during extraction
                progress = 20 + (i / len(ingestor.file_meta_queue)) * 20
                self.log_progress(2, f"Extracting: {fmeta.file_name}", int(progress))
            
            success_count = sum(1 for f in extracted if f.status == "success")
            fail_count = len(extracted) - success_count
            
            if success_count == 0:
                self.results.update({
                    "status": "error",
                    "message": "No files could be processed successfully.",
                    "errors": [f"Failed to extract content from {fail_count} files"]
                })
                return self.results
            
            # 3. Embedding
            self.log_progress(3, "Creating semantic embeddings...", 40)
            embedder = EmbeddingAgent()
            embedded = []
            
            for i, extracted_file in enumerate(extracted):
                embedded_file = embedder.embed(extracted_file)
                embedded.append(embedded_file)
                
                progress = 40 + (i / len(extracted)) * 20
                self.log_progress(3, f"Embedding: {extracted_file.file_meta.file_name}", int(progress))
            
            embedded_count = len([e for e in embedded if e.status == "embedded"])
            
            if embedded_count < 2:
                self.results.update({
                    "status": "error",
                    "message": "Not enough files could be embedded for clustering.",
                    "errors": ["Need at least 2 valid embeddings for clustering"]
                })
                return self.results
            
            # 4. Clustering
            self.log_progress(4, "Clustering files by semantic similarity...", 60)
            clusterer = ClusteringAgent(fallback_k_range=(2, 10), min_cluster_size=2)
            clustered = clusterer.cluster(embedded)
            
            if not clustered:
                self.results.update({
                    "status": "error",
                    "message": "Clustering failed.",
                    "errors": ["Could not create semantic clusters from the files"]
                })
                return self.results
            
            cluster_map = defaultdict(list)
            for f in clustered:
                cluster_map[f.cluster_id].append(f)
            
            self.results["clusters_found"] = len(cluster_map)
            
            # 5. Folder Naming
            self.log_progress(5, "Generating intelligent folder names...", 80)
            naming_agent = FolderNamingAgent()
            folder_names = naming_agent.name_clusters(cluster_map)
            
            # 5.1 Merge Similar Clusters
            self.log_progress(5, "Optimizing cluster organization...", 85)
            cluster_map = clusterer.merge_similar_clusters(cluster_map, folder_names)
            folder_names = naming_agent.name_clusters(cluster_map)
            
            # Prepare folder structure for output
            folders_info = []
            for cluster_id, files in sorted(cluster_map.items()):
                folder_name = folder_names.get(cluster_id, f"cluster_{cluster_id}")
                file_names = [f.file_meta.file_name for f in files]
                folders_info.append({
                    "name": folder_name,
                    "cluster_id": cluster_id,
                    "files": file_names,
                    "file_count": len(file_names)
                })
            
            self.results["folders_created"] = folders_info
            
            # 6. File Relocation (if not dry run)
            if not dry_run:
                self.log_progress(6, "Relocating files to organized folders...", 90)
                relocation_agent = FileRelocationAgent(
                    base_destination_dir=str(self.input_folder),
                    dry_run=False
                )
                relocation_results = relocation_agent.relocate_files(cluster_map)

                if relocation_results["errors"]:
                    self.results["errors"].extend(relocation_results["errors"])

                # Persist faiss index so the daemon can do incremental assignment
                self.log_progress(6, "Building incremental assignment index...", 95)
                self._persist_index(cluster_map, folder_names)
            else:
                self.log_progress(6, "Dry run complete - no files moved", 95)

            # Final results
            self.results.update({
                "status": "success",
                "message": f"Successfully organized {self.results['files_processed']} files into {len(folders_info)} semantic folders.",
                "progress": 100,
                "stats": {
                    "files_ingested": len(ingestor.file_meta_queue),
                    "files_extracted": success_count,
                    "extraction_failures": fail_count,
                    "files_embedded": embedded_count,
                    "files_clustered": len(clustered),
                    "final_clusters": len(cluster_map),
                    "dry_run": dry_run
                }
            })
            
            return self.results
            
        except Exception as e:
            self.results.update({
                "status": "error",
                "message": f"Pipeline failed: {str(e)}",
                "errors": [str(e)]
            })
            return self.results

    def _persist_index(self, cluster_map: dict, folder_names: dict) -> None:
        """Build and save the faiss index using post-relocation file paths."""
        try:
            import numpy as np
            from backend.agents.index_manager import save_index

            embeddings, labels, new_paths, cluster_folders = [], [], [], {}

            for cid, files in cluster_map.items():
                if cid == -1:
                    continue
                fname = folder_names.get(cid, f"cluster_{cid}")
                folder_abs = str(self.input_folder / fname)
                cluster_folders[cid] = folder_abs

                for f in files:
                    if not f.embedding:
                        continue
                    embeddings.append(f.embedding)
                    labels.append(cid)
                    new_path = str(Path(folder_abs) / Path(f.file_meta.file_path).name)
                    new_paths.append(new_path)

            if embeddings:
                save_index(
                    np.array(embeddings, dtype=np.float32),
                    np.array(labels),
                    new_paths,
                    cluster_folders,
                )
        except Exception as exc:
            self.results["errors"].append(f"Index persistence failed: {exc}")


def main():
    """Command line interface for Tauri integration."""
    parser = argparse.ArgumentParser(description='Production Semantic File Sorter')
    parser.add_argument('folder_path', help='Path to the folder to sort')
    parser.add_argument('--preview', action='store_true', 
                       help='Preview mode - estimate clusters without processing')
    parser.add_argument('--dry-run', action='store_true',
                       help='Run pipeline without actually moving files')
    parser.add_argument('--max-files', type=int, default=None,
                       help='Cap files with stratified sampling across file types')

    args = parser.parse_args()

    try:
        pipeline = TauriPipeline(args.folder_path)

        if args.preview:
            result = pipeline.preview_clusters()
        else:
            result = pipeline.run_full_pipeline(dry_run=args.dry_run, max_files=args.max_files)
        
        # Output JSON for Tauri to consume
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        error_result = {
            "status": "error",
            "message": f"Failed to initialize pipeline: {str(e)}",
            "errors": [str(e)]
        }
        print(json.dumps(error_result, indent=2))
        sys.exit(1)

if __name__ == '__main__':
    main()