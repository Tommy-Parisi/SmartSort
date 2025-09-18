import argparse
import json
import os
import glob
from pathlib import Path

def preview_clusters(folder, include_subfolders=True):
    """Preview mode - count files and estimate clusters"""
    try:
        folder_path = Path(folder)
        if not folder_path.exists():
            return 0
        
        # Count files in the folder
        files = []
        for ext in ['*.txt', '*.pdf', '*.doc', '*.docx', '*.jpg', '*.jpeg', '*.png', '*.gif']:
            files.extend(glob.glob(str(folder_path / ext)))
            if include_subfolders:
                files.extend(glob.glob(str(folder_path / '**' / ext), recursive=True))
        
        # Simple clustering estimate based on file count
        if len(files) == 0:
            return 0
        elif len(files) <= 5:
            return 1
        elif len(files) <= 20:
            return 2
        elif len(files) <= 50:
            return 3
        else:
            return min(len(files) // 10 + 1, 10)  # Max 10 clusters
            
    except Exception as e:
        print(f"Error in preview: {e}")
        return 0

def sort_and_return_structure(folder, include_subfolders=True):
    """Sort files and return folder structure"""
    try:
        folder_path = Path(folder)
        if not folder_path.exists():
            return {"folders": []}
        
        # Get all files
        files = []
        for ext in ['*.txt', '*.pdf', '*.doc', '*.docx', '*.jpg', '*.jpeg', '*.png', '*.gif']:
            files.extend(glob.glob(str(folder_path / ext)))
            if include_subfolders:
                files.extend(glob.glob(str(folder_path / '**' / ext), recursive=True))
        
        if not files:
            return {"folders": []}
        
        # Simple sorting by file extension
        file_groups = {}
        for file_path in files:
            ext = Path(file_path).suffix.lower()
            if ext not in file_groups:
                file_groups[ext] = []
            file_groups[ext].append(Path(file_path).name)
        
        # Create folder structure
        folders = []
        for ext, file_list in file_groups.items():
            folder_name = f"{ext[1:].upper()} Files" if ext else "Other Files"
            folders.append({
                "name": folder_name,
                "files": file_list
            })
        
        return {"folders": folders}
        
    except Exception as e:
        print(f"Error in sort: {e}")
        return {"folders": []}

def main():
    parser = argparse.ArgumentParser(description="Run the Synapse Sorter pipeline.")
    parser.add_argument("folder", help="Path to the folder to sort")
    parser.add_argument("--preview", action="store_true", help="Preview mode - only show cluster count")
    parser.add_argument("--json", action="store_true", help="Output folder structure as JSON")
    parser.add_argument("--sensitivity", choices=["low", "medium", "high"], default="medium", help="Cluster sensitivity")
    parser.add_argument("--naming-style", choices=["simple", "descriptive", "detailed"], default="simple", help="Folder naming style")
    parser.add_argument("--include-subfolders", action="store_true", help="Include subfolders in processing")
    parser.add_argument("--no-subfolders", action="store_true", help="Exclude subfolders from processing")
    
    args = parser.parse_args()
    
    # Determine if subfolders should be included
    include_subfolders = args.include_subfolders or not args.no_subfolders
    
    print(f"[Python] Running sorter on: {args.folder}")
    print(f"[Python] Preview mode: {args.preview}")
    print(f"[Python] Sensitivity: {args.sensitivity}")
    print(f"[Python] Naming style: {args.naming_style}")
    print(f"[Python] Include subfolders: {include_subfolders}")
    
    if args.preview:
        clusters = preview_clusters(args.folder, include_subfolders)
        print(clusters)
    elif args.json:
        structure = sort_and_return_structure(args.folder, include_subfolders)
        print(json.dumps(structure))
    else:
        # Default mode - just run the sort
        structure = sort_and_return_structure(args.folder, include_subfolders)
        print(json.dumps(structure))

if __name__ == "__main__":
    main()
