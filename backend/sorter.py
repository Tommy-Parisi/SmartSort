import argparse
from pipeline.cli import run_pipeline  

def main():
    parser = argparse.ArgumentParser(description="Run the Synapse Sorter pipeline.")
    parser.add_argument("folder", help="Path to the folder to sort")
    args = parser.parse_args()
    
    print(f"[Python] Running sorter on: {args.folder}")
    run_pipeline(args.folder)

if __name__ == "__main__":
    main()
