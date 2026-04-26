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
from backend.core.models import FileContent, ClusteredFile
from backend.core.license import check_file_limit, activate, license_status
from dotenv import load_dotenv
from datetime import datetime
import random

load_dotenv()


def _stratified_sample(file_metas, max_files: int, seed: int = 42):
    """Equal-per-type stratified sample — no single type can dominate the budget.

    Types are processed smallest-first; any type that exhausts before its slot
    allocation donates the remainder to the remaining types.
    """
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


def _build_photo_clusters(photo_embedded: list, next_cluster_id: int) -> tuple:
    """Group photo EmbeddedFiles by year into synthetic clusters.

    Returns (cluster_map_additions, folder_names_additions).
    """
    buckets: dict = defaultdict(list)
    for pf in photo_embedded:
        buckets[pf.raw_text].append(pf)

    new_clusters: dict = {}
    new_names: dict = {}
    cid = next_cluster_id

    for date_bucket, pfiles in sorted(buckets.items()):
        folder_name = "Photos" if date_bucket == "unknown" else f"Photos {date_bucket}"

        cluster_files = [
            ClusteredFile(
                file_meta=pf.file_meta,
                embedding=None,
                raw_text=date_bucket,
                cluster_id=cid,
                status="clustered",
            )
            for pf in pfiles
        ]
        new_clusters[cid] = cluster_files
        new_names[cid] = folder_name
        cid += 1

    return new_clusters, new_names


def _build_screenshot_cluster(screenshot_embedded: list, next_cluster_id: int) -> tuple:
    """Group all screenshots into a single Screenshots folder."""
    if not screenshot_embedded:
        return {}, {}
    cluster_files = [
        ClusteredFile(
            file_meta=pf.file_meta,
            embedding=None,
            raw_text="screenshot",
            cluster_id=next_cluster_id,
            status="clustered",
        )
        for pf in screenshot_embedded
    ]
    return {next_cluster_id: cluster_files}, {next_cluster_id: "Screenshots"}


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

            # License check — trial mode caps at 500 files
            license_check = check_file_limit(len(ingestor.file_meta_queue))
            if not license_check["allowed"]:
                self.results.update({
                    "status": "trial_limit",
                    "message": (
                        f"Trial mode is limited to {license_check['limit']} files. "
                        f"This folder has {license_check['count']} files. "
                        "Upgrade to FileSort Pro for unlimited sorting."
                    ),
                    "trial_limit": license_check["limit"],
                    "file_count": license_check["count"],
                })
                return self.results

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
            photo_embedded      = [e for e in embedded if e.status == "photo"]
            screenshot_embedded = [e for e in embedded if e.status == "screenshot"]

            if embedded_count < 2 and not photo_embedded and not screenshot_embedded:
                self.results.update({
                    "status": "error",
                    "message": "Not enough files could be embedded for clustering.",
                    "errors": ["Need at least 2 valid embeddings for clustering"]
                })
                return self.results

            # 4. Clustering
            self.log_progress(4, "Clustering files by semantic similarity...", 60)
            clusterer = ClusteringAgent(fallback_k_range=(2, 10), min_cluster_size=2)
            if embedded_count >= 2:
                clustered = clusterer.cluster(embedded)
                if not clustered:
                    self.results.update({
                        "status": "error",
                        "message": "Clustering failed.",
                        "errors": ["Could not create semantic clusters from the files"]
                    })
                    return self.results
            else:
                clustered = []

            cluster_map = defaultdict(list)
            for f in clustered:
                cluster_map[f.cluster_id].append(f)

            self.results["clusters_found"] = len(cluster_map)

            # 5. Folder Naming
            self.log_progress(5, "Generating intelligent folder names...", 80)
            naming_agent = FolderNamingAgent()
            folder_names: dict = {}
            if cluster_map:
                folder_names = naming_agent.name_clusters(cluster_map)

                # 5.1 Merge Similar Clusters
                self.log_progress(5, "Optimizing cluster organization...", 85)
                cluster_map = clusterer.merge_similar_clusters(cluster_map, folder_names)
                folder_names = naming_agent.name_clusters(cluster_map)

            # Inject photo and screenshot synthetic clusters after merge
            next_id = max(cluster_map.keys(), default=-1) + 1
            photo_clusters = {}
            if photo_embedded:
                photo_clusters, photo_names = _build_photo_clusters(photo_embedded, next_id)
                cluster_map.update(photo_clusters)
                folder_names.update(photo_names)
                next_id = max(cluster_map.keys(), default=-1) + 1

            screenshot_clusters = {}
            if screenshot_embedded:
                screenshot_clusters, screenshot_names = _build_screenshot_cluster(screenshot_embedded, next_id)
                cluster_map.update(screenshot_clusters)
                folder_names.update(screenshot_names)
            
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

    # ── Streaming / event-driven mode ─────────────────────────────────────

    def _emit(self, event: str, payload: dict) -> None:
        """Write a single NDJSON event line to stdout and flush immediately."""
        print(json.dumps({"event": event, "payload": payload}), flush=True)

    def run_streaming_pipeline(self, dry_run: bool = False, max_files: int = None) -> None:
        """Run the pipeline and emit NDJSON events to stdout for Tauri to consume.

        Unlike run_full_pipeline(), this method does NOT return a final JSON blob.
        Everything is communicated via _emit() calls.
        """
        try:
            # 1. Ingestion
            ingestor = IngestionManager(str(self.input_folder))
            ingestor.scan()

            if not ingestor.file_meta_queue:
                self._emit("sort-complete", {
                    "folders_created": 0,
                    "files_sorted": 0,
                    "files_unsorted": 0,
                    "folder_tree": {"folders": []}
                })
                return

            if max_files is not None and len(ingestor.file_meta_queue) > max_files:
                ingestor.file_meta_queue = _stratified_sample(ingestor.file_meta_queue, max_files)

            # License check
            license_check = check_file_limit(len(ingestor.file_meta_queue))
            if not license_check["allowed"]:
                self._emit("sort-error", {
                    "code": "trial_limit",
                    "message": (
                        f"trial_limit: folder contains {license_check['count']} files, "
                        f"trial limit is {license_check['limit']}."
                    ),
                    "trial_limit": license_check["limit"],
                    "file_count": license_check["count"],
                })
                return

            num_files = len(ingestor.file_meta_queue)
            
            # extraction+embedding take 75% of bar, naming+placing take 25%
            W_EXT, W_EMB, W_NAM, W_PLC = 35, 40, 15, 10
            files_total = num_files * (W_EXT + W_EMB + W_NAM + W_PLC)
            current_processed = 0

            # 2. Extraction — 40% of bar
            router = ExtractorRouter()
            extracted = []
            for i, fmeta in enumerate(ingestor.file_meta_queue):
                current_processed += W_EXT
                self._emit("file-assigned", {
                    "filename": fmeta.file_name,
                    "cluster_id": -1,
                    "folder_name": "",
                    "files_processed": current_processed,
                    "files_total": files_total,
                    "stage": "extracting",
                })
                content: FileContent = router.route(fmeta)
                extracted.append(content)

            success_count = sum(1 for f in extracted if f.status == "success")
            if success_count == 0:
                self._emit("sort-error", {"message": "No files could be extracted."})
                return

            # 3. Embedding — 40% of bar (Total so far: 80%)
            embedder = EmbeddingAgent()
            embedded = []
            for i, extracted_file in enumerate(extracted):
                current_processed += W_EMB
                self._emit("file-assigned", {
                    "filename": extracted_file.file_meta.file_name,
                    "cluster_id": -1,
                    "folder_name": "",
                    "files_processed": current_processed,
                    "files_total": files_total,
                    "stage": "embedding",
                })
                embedded_file = embedder.embed(extracted_file)
                embedded.append(embedded_file)

            embedded_count      = len([e for e in embedded if e.status == "embedded"])
            photo_embedded      = [e for e in embedded if e.status == "photo"]
            screenshot_embedded = [e for e in embedded if e.status == "screenshot"]

            if embedded_count < 2 and not photo_embedded and not screenshot_embedded:
                self._emit("sort-error", {"message": "Not enough files could be embedded for clustering."})
                return

            # Signal the start of the 'Thinking' phase
            self._emit("file-assigned", {
                "filename": "Semantic Clustering",
                "cluster_id": -1,
                "folder_name": "",
                "files_processed": current_processed,
                "files_total": files_total,
                "stage": "clustering",
            })

            # 4. Clustering (batch)
            clusterer = ClusteringAgent(fallback_k_range=(2, 10), min_cluster_size=2)
            if embedded_count >= 2:
                clustered = clusterer.cluster(embedded)
                if not clustered:
                    self._emit("sort-error", {"message": "Clustering failed."})
                    return
            else:
                clustered = []

            cluster_map = defaultdict(list)
            for f in clustered:
                cluster_map[f.cluster_id].append(f)

            # 5. Folder Naming — 10% of bar (Total so far: 90%)
            naming_agent = FolderNamingAgent()
            folder_names: dict = {}
            if cluster_map:
                folder_names = naming_agent.name_clusters(cluster_map)
                cluster_map = clusterer.merge_similar_clusters(cluster_map, folder_names)
                folder_names = naming_agent.name_clusters(cluster_map)

            next_id = max(cluster_map.keys(), default=-1) + 1
            photo_clusters = {}
            if photo_embedded:
                photo_clusters, photo_names = _build_photo_clusters(photo_embedded, next_id)
                cluster_map.update(photo_clusters)
                folder_names.update(photo_names)
                next_id = max(cluster_map.keys(), default=-1) + 1

            screenshot_clusters = {}
            if screenshot_embedded:
                screenshot_clusters, screenshot_names = _build_screenshot_cluster(screenshot_embedded, next_id)
                cluster_map.update(screenshot_clusters)
                folder_names.update(screenshot_names)

            # Emit folder-discovered
            for cluster_id, files in sorted(cluster_map.items()):
                if cluster_id == -1: continue
                folder_name = folder_names.get(cluster_id, f"cluster_{cluster_id}")
                self._emit("folder-discovered", {
                    "cluster_id": cluster_id,
                    "folder_name": folder_name,
                    "estimated_capacity": len(files),
                })

            # Process all files in naming stage to reach 90%
            all_files = (
                list(clustered)
                + [f for files in photo_clusters.values() for f in files]
                + [f for files in screenshot_clusters.values() for f in files]
            )
            for f in all_files:
                current_processed += W_NAM
                folder_name = folder_names.get(f.cluster_id, "Unsorted") if f.cluster_id != -1 else "Unsorted"
                self._emit("file-assigned", {
                    "filename": f.file_meta.file_name,
                    "cluster_id": f.cluster_id,
                    "folder_name": folder_name,
                    "files_processed": current_processed,
                    "files_total": files_total,
                    "stage": "naming",
                })

            # Build folder tree for final event
            folder_tree_entries = []
            for cluster_id, files in sorted(cluster_map.items()):
                if cluster_id == -1: continue
                folder_name = folder_names.get(cluster_id, f"cluster_{cluster_id}")
                file_entries = []
                for f in files:
                    ext = Path(f.file_meta.file_name).suffix.lstrip('.')
                    file_entries.append({"name": f.file_meta.file_name, "extension": ext})
                folder_tree_entries.append({
                    "cluster_id": cluster_id,
                    "folder_name": folder_name,
                    "files": file_entries,
                })

            # 6. File Relocation — Final 10% of bar
            if not dry_run:
                relocation_agent = FileRelocationAgent(base_destination_dir=str(self.input_folder), dry_run=False)
                relocation_agent.relocate_files(cluster_map)

            for f in all_files:
                current_processed += W_PLC
                folder_name = folder_names.get(f.cluster_id, "Unsorted") if f.cluster_id != -1 else "Unsorted"
                self._emit("file-assigned", {
                    "filename": f.file_meta.file_name,
                    "cluster_id": f.cluster_id,
                    "folder_name": folder_name,
                    "files_processed": current_processed,
                    "files_total": files_total,
                    "stage": "placing",
                })

            if not dry_run:
                self._persist_index(cluster_map, folder_names)

            unsorted_count = sum(1 for f in clustered if f.cluster_id == -1)
            photo_sorted      = sum(len(files) for files in photo_clusters.values())
            screenshot_sorted = sum(len(files) for files in screenshot_clusters.values())
            sorted_count = len(clustered) - unsorted_count + photo_sorted + screenshot_sorted

            self._emit("sort-complete", {
                "folders_created": len(folder_tree_entries),
                "files_sorted": sorted_count,
                "files_unsorted": unsorted_count,
                "folder_tree": {"folders": folder_tree_entries},
            })

        except Exception as e:
            self._emit("sort-error", {"message": f"Pipeline failed: {str(e)}"})

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
            pass


def apply_preview(base_folder: str, preview_folders: list,
                  trashed_filenames: list | None = None) -> dict:
    """Apply user-edited preview assignments to disk and log moves for undo.
    Files in trashed_filenames are permanently deleted from base_folder."""
    import shutil
    from datetime import datetime, timezone

    base = Path(base_folder)
    smartsort_dir = Path.home() / ".smartsort"
    smartsort_dir.mkdir(parents=True, exist_ok=True)
    move_log = smartsort_dir / "move_log.jsonl"

    moved = 0
    deleted = 0
    errors = []

    for folder in preview_folders:
        folder_name = (folder.get("name") or "").strip()
        files = folder.get("files") or []
        if not folder_name or not files:
            continue

        dest_dir = base / folder_name
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            errors.append(f"Cannot create '{dest_dir}': {exc}")
            continue

        for file in files:
            filename = (file.get("filename") or "").strip()
            if not filename:
                continue
            src = base / filename
            if not src.exists():
                errors.append(f"File found in preview but not on disk: {src}")
                continue

            dest = dest_dir / filename
            if dest.exists():
                stem, suffix = src.stem, src.suffix
                i = 1
                while dest.exists():
                    dest = dest_dir / f"{stem}_{i}{suffix}"
                    i += 1

            try:
                shutil.move(str(src), str(dest))
                moved += 1
                entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": str(src),
                    "destination": str(dest),
                    "cluster_id": folder.get("cluster_id", -1),
                    "similarity": 1.0,
                }
                with open(move_log, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except Exception as exc:
                errors.append(f"Failed to move '{src}': {exc}")

    # Delete trashed files
    for filename in (trashed_filenames or []):
        src = base / filename
        if src.exists():
            try:
                src.unlink()
                deleted += 1
            except Exception as exc:
                errors.append(f"Failed to delete '{src}': {exc}")

    return {"status": "done", "moved": moved, "deleted": deleted, "errors": errors}


def undo_last_sort() -> dict:
    """Reverse all moves recorded in move_log.jsonl, then clear the log."""
    import shutil

    move_log = Path.home() / ".smartsort" / "move_log.jsonl"
    if not move_log.exists():
        return {"status": "done", "reversed": 0, "errors": []}

    entries = []
    with open(move_log) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    reversed_count = 0
    errors = []
    for entry in reversed(entries):
        src = entry.get("destination", "")
        dst = entry.get("source", "")
        if not src or not dst:
            continue
        try:
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
            reversed_count += 1
        except Exception as exc:
            errors.append(f"Failed to reverse '{src}' → '{dst}': {exc}")

    move_log.unlink(missing_ok=True)
    return {"status": "done", "reversed": reversed_count, "errors": errors}


def main():
    """Command line interface for Tauri integration."""
    parser = argparse.ArgumentParser(description='Production Semantic File Sorter')
    parser.add_argument('folder_path', nargs='?', help='Path to the folder to sort')
    parser.add_argument('--preview', action='store_true',
                       help='Preview mode - estimate clusters without processing')
    parser.add_argument('--dry-run', action='store_true',
                       help='Run pipeline without actually moving files')
    parser.add_argument('--stream-events', action='store_true',
                       help='Emit NDJSON events to stdout during processing (for Tauri)')
    parser.add_argument('--max-files', type=int, default=None,
                       help='Cap files with stratified sampling across file types')
    parser.add_argument('--activate', metavar='LICENSE_KEY',
                       help='Activate FileSort Pro with a license key')
    parser.add_argument('--license-status', action='store_true',
                       help='Print current license status and exit')
    parser.add_argument('--undo', action='store_true',
                       help='Undo the last sort by reversing move_log.jsonl')
    parser.add_argument('--apply-preview', action='store_true',
                       help='Apply user-confirmed preview assignments to disk')
    parser.add_argument('--base-folder', metavar='PATH',
                       help='Base folder for --apply-preview')
    parser.add_argument('--preview-json', metavar='JSON',
                       help='JSON array of preview folders for --apply-preview')
    parser.add_argument('--trashed-json', metavar='JSON',
                       help='JSON array of filenames to permanently delete at apply-preview time')
    parser.add_argument('--daemon-status', action='store_true',
                       help='Print daemon status as JSON and exit')
    parser.add_argument('--start-daemon', metavar='FOLDERS_JSON',
                       help='Start the watch daemon for the given JSON array of folders')
    parser.add_argument('--stop-daemon', action='store_true',
                       help='Stop the running watch daemon')

    args = parser.parse_args()

    # ── Daemon management ─────────────────────────────────────────────────────
    if args.daemon_status:
        try:
            from backend.daemon.watcher import get_daemon_status
            print(json.dumps(get_daemon_status()))
        except Exception as e:
            print(json.dumps({"running": False, "watchedFolders": [], "recentActivity": []}))
        sys.exit(0)

    if args.start_daemon:
        try:
            folders = json.loads(args.start_daemon)
            from backend.daemon.watcher import start_daemon
            start_daemon(folders)
            print(json.dumps({"status": "started"}))
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}))
            sys.exit(1)
        sys.exit(0)

    if args.stop_daemon:
        try:
            from backend.daemon.watcher import stop_daemon
            stop_daemon()
            print(json.dumps({"status": "stopped"}))
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(0)

    # ── License management ────────────────────────────────────────────────────
    if args.license_status:
        print(json.dumps(license_status()))
        sys.exit(0)

    if args.activate:
        ok = activate(args.activate)
        if ok:
            print(json.dumps({"status": "activated", "message": "License activated. FileSort Pro is now unlimited."}))
        else:
            print(json.dumps({"status": "error", "message": "Invalid license key. Keys must be UUID4 format."}))
            sys.exit(1)
        sys.exit(0)

    if args.undo:
        try:
            result = undo_last_sort()
            print(json.dumps(result))
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}))
            sys.exit(1)
        sys.exit(0)

    if args.apply_preview:
        if not args.base_folder or not args.preview_json:
            print(json.dumps({"status": "error", "message": "--base-folder and --preview-json are required"}))
            sys.exit(1)
        try:
            folders = json.loads(args.preview_json)
            trashed = json.loads(args.trashed_json) if args.trashed_json else None
            result = apply_preview(args.base_folder, folders, trashed)
            print(json.dumps(result))
            if result["errors"] and result["moved"] == 0 and result.get("deleted", 0) == 0:
                sys.exit(1)
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}))
            sys.exit(1)
        sys.exit(0)

    # ── Pipeline ──────────────────────────────────────────────────────────────
    try:
        pipeline = TauriPipeline(args.folder_path)

        if args.stream_events:
            # Streaming mode: emit NDJSON events to stdout, no final JSON blob
            pipeline.run_streaming_pipeline(dry_run=args.dry_run, max_files=args.max_files)
        elif args.preview:
            result = pipeline.preview_clusters()
            print(json.dumps(result, indent=2))
        else:
            result = pipeline.run_full_pipeline(dry_run=args.dry_run, max_files=args.max_files)
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