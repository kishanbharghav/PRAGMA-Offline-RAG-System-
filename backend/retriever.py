import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"

import chromadb
from reranker import rerank
from intent_processor import process_query
from entity_detector import detect_entities
from generator import generate_answer
from sentence_transformers import SentenceTransformer

CHROMA_PATH = "database"
COLLECTION_NAME = "docuvault"

print("Loading embedding model...")
embedding_model = SentenceTransformer("BAAI/bge-small-en", local_files_only=True)

# Load database
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_collection(name=COLLECTION_NAME)


def search(query, top_k=5):

    from intent_processor import process_query
    expanded_query = process_query(query)
    print(f"\nFinal Query → {expanded_query}")


    query_embedding = embedding_model.encode(
        "query: " + query,
        normalize_embeddings=True
    )
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=10
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    reranked = rerank(expanded_query, documents, metadatas, top_k=top_k)

    for doc, meta, score in reranked:
        entities = detect_entities(doc)
        if entities["emails"] or entities["phones"] or entities["urls"]:
            print("\nStructured data detected:")
            print(entities)

    return reranked



# ---------------- TEST ----------------
if __name__ == "__main__":
    while True:
        query = input("\nAsk something about the PDF: ")

        results = search(query)

        contexts = [doc for doc, meta, score in results[:10]]
        pages = [meta["page"] for doc, meta, score in results[:7]]

        answer = generate_answer(query, contexts, pages)

        print("\n📄 Answer:\n")
        print(answer)

