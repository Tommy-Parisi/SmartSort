def run_pipeline(input_folder):
    # 1. Ingestion
    #ingestor = IngestionManager(input_folder)
    #ingestor.scan()
    #files = ingestor.file_meta_queue

    # 2. Extraction
    #router = ExtractorRouter()
    #extracted = [router.route(f) for f in files]

    # 3. Embedding
    #embedder = EmbeddingAgent()
    #embedded = [embedder.embed(f) for f in extracted]

    # 4. Clustering
    #clusterer = ClusteringAgent()
    #clustered = clusterer.cluster(embedded)

    # 5. Naming
    #naming_agent = FolderNamingAgent()
    #clusters = group_by_cluster_id(clustered)
    #folder_names = naming_agent.name_clusters(clusters)

    # 6. Relocation
    #mover = FileRelocationAgent()
    #mover.move_files(clustered, folder_names)
