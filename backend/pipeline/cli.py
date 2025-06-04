import argparse
from pipeline.run_pipeline import run_pipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", help="Path to input folder")
    args = parser.parse_args()
    run_pipeline(args.folder)
