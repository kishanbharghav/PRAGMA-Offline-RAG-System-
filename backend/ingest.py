import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"

import fitz  # PyMuPDF
import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import os
import uuid
from entity_detector import detect_entities


# -----------------------------
# CONFIG
# -----------------------------

PDF_PATH = "sample.pdf"
CHROMA_PATH = "database"
COLLECTION_NAME = "docuvault"

# -----------------------------
# Initialize Embedding Model
# -----------------------------

print("Loading embedding model...")
embedding_model = SentenceTransformer("BAAI/bge-small-en", local_files_only=True)

# -----------------------------
# Initialize Chroma (Persistent)
# -----------------------------

chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)

# -----------------------------
# Text Extraction
# -----------------------------

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    pages = []

    for page_number in range(len(doc)):
        page = doc[page_number]
        text = page.get_text()
        pages.append((page_number + 1, text))

    return pages

# -----------------------------
# Chunking Function
# -----------------------------

def chunk_text(text, max_chars=900):
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) < max_chars:
            current_chunk += " " + para
        else:
            chunks.append(current_chunk.strip())
            current_chunk = para

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


# -----------------------------
# Ingestion Pipeline
# -----------------------------

def ingest(pdf_path):
    pages = extract_text_from_pdf(pdf_path)

    print("Processing pages...")
    for page_number, text in tqdm(pages):

        if not text.strip():
            continue

        chunks = chunk_text(text)

        for chunk in chunks:
            embedding = embedding_model.encode(
            "passage: " + chunk,
            normalize_embeddings=True
            ).tolist()

            collection.add(
                documents=[chunk],
                embeddings=[embedding],
                metadatas=[{"page": page_number}],
                ids=[str(uuid.uuid4())]
            )

            entities = detect_entities(chunk)

            # index URLs separately so semantic search can find them
            for url in entities["urls"]:
                anchor_text = f"Link mentioned in document: {url}"

                collection.add(
                    documents=[anchor_text],
                    embeddings=[embedding_model.encode(anchor_text).tolist()],
                    metadatas=[{"page": page_number, "type": "url"}],
                    ids=[str(uuid.uuid4())]
                )


    print("Ingestion complete.")

# -----------------------------
# Run
# -----------------------------

if __name__ == "__main__":
    ingest(PDF_PATH)
