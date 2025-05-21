from agents.ingestion_manager import IngestionManager
from agents.extractor_router import ExtractorRouter
from agents.embedding_agent import EmbeddingAgent
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

    # 3. Embedding
    embedder = EmbeddingAgent()
    embedded = []

    for extracted_file in extracted:
        embedded_file = embedder.embed(extracted_file)
        embedded.append(embedded_file)

    print(f"\nEmbedded {len([e for e in embedded if e.status == 'embedded'])} documents successfully.")

    # Print a few example embeddings
    print("\n--- Sample Embeddings ---")

    for embedded_file in embedded[:25]:  # Show first 5 for sanity
        if embedded_file.status == "embedded":
            print(f"{embedded_file.file_meta.file_name}")
            print(f"Embedding (first 5 values): {embedded_file.embedding[:5]}")
            print(f"Vector length: {len(embedded_file.embedding)}\n")

