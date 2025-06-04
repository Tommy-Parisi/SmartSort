import os
import shutil
from typing import Dict, List
from core.models import ClusteredFile
from core.utils import log_error
from .folder_naming_agent import FolderNamingAgent

class FileRelocationAgent:
    def __init__(self, base_destination_dir: str, dry_run: bool = False):
        """
        Initialize the FileRelocationAgent.
        
        Args:
            base_destination_dir: The root directory where cluster folders will be created
            dry_run: If True, only simulate the operations without actually moving files
        """
        self.base_destination_dir = os.path.abspath(base_destination_dir)
        self.dry_run = dry_run
        self.folder_namer = FolderNamingAgent()
        
    def relocate_files(self, cluster_map: Dict[int, List[ClusteredFile]]) -> Dict[str, List[str]]:
        """
        Relocate files into their respective cluster folders.
        
        Args:
            cluster_map: Dictionary mapping cluster IDs to lists of ClusteredFile objects
            
        Returns:
            Dictionary containing success and error messages
        """
        results = {
            "success": [],
            "errors": []
        }
        
        # Get folder names for each cluster
        folder_names = self.folder_namer.name_clusters(cluster_map)
        
        # Process each cluster
        for cluster_id, files in cluster_map.items():
            folder_name = folder_names.get(cluster_id, f"cluster_{cluster_id}")
            destination_dir = os.path.join(self.base_destination_dir, folder_name)
            
            # Create destination directory if it doesn't exist
            if not self.dry_run:
                try:
                    os.makedirs(destination_dir, exist_ok=True)
                except Exception as e:
                    error_msg = f"Failed to create directory {destination_dir}: {str(e)}"
                    log_error(f"[FileRelocationAgent] {error_msg}")
                    results["errors"].append(error_msg)
                    continue

            # Move each file in the cluster
            for file in files:
                source_path = file.file_meta.file_path
                if not os.path.exists(source_path):
                    error_msg = f"Source file not found: {source_path}"
                    log_error(f"[FileRelocationAgent] {error_msg}")
                    results["errors"].append(error_msg)
                    continue
                
                dest_path = os.path.join(destination_dir, os.path.basename(source_path))
                
                try:
                    if not self.dry_run:
                        shutil.move(source_path, dest_path)
                    results["success"].append(f"Moved {source_path} to {dest_path}")
                except Exception as e:
                    error_msg = f"Failed to move {source_path} to {dest_path}: {str(e)}"
                    log_error(f"[FileRelocationAgent] {error_msg}")
                    results["errors"].append(error_msg)
        
        return results
