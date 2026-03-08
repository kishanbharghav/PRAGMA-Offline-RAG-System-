import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"

from sentence_transformers import CrossEncoder

print("Loading reranker model...")
reranker_model = CrossEncoder(
    "BAAI/bge-reranker-base",
    local_files_only=True
)


def rerank(query, documents, metadatas, top_k=3):

    pairs = [[query, doc] for doc in documents]
    scores = reranker_model.predict(pairs)

    scored = list(zip(documents, metadatas, scores))
    scored.sort(key=lambda x: x[2], reverse=True)

    return scored[:top_k]