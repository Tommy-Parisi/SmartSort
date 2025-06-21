import argparse
from pipeline.cli import run_pipeline  

def main():
    parser = argparse.ArgumentParser(description="Run the Synapse Sorter pipeline.")
    parser.add_argument("folder", help="Path to the folder to sort")
    parser.add_argument("--preview", action="store_true", help="Preview mode - only show cluster count")
    parser.add_argument("--sensitivity", choices=["low", "medium", "high"], default="medium", help="Cluster sensitivity")
    parser.add_argument("--naming-style", choices=["simple", "descriptive", "detailed"], default="simple", help="Folder naming style")
    parser.add_argument("--include-subfolders", action="store_true", help="Include subfolders in processing")
    parser.add_argument("--no-subfolders", action="store_true", help="Exclude subfolders from processing")
    
    args = parser.parse_args()
    
    print(f"[Python] Running sorter on: {args.folder}")
    print(f"[Python] Preview mode: {args.preview}")
    print(f"[Python] Sensitivity: {args.sensitivity}")
    print(f"[Python] Naming style: {args.naming_style}")
    print(f"[Python] Include subfolders: {args.include_subfolders}")
    
    if args.preview:
        # For preview mode, just return a mock cluster count
        print("Found 5 clusters")
    else:
        run_pipeline(args.folder)

if __name__ == "__main__":
    main()
