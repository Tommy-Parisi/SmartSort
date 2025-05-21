from agents.ingestion_manager import IngestionManager
from agents.extractor_router import ExtractorRouter
from core.models import FileContent

def run_pipeline(input_folder: str, debug_preview: bool = True):
    print(f"\n Starting pipeline on: {input_folder}\n")

    # 1. Ingestion
    ingestor = IngestionManager(input_folder)
    ingestor.scan()

    if not ingestor.file_meta_queue:
        print("  No files found. Check your folder path or filters.")
        return

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
