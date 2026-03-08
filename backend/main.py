import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import chromadb
import shutil
import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer
import uuid
import json

from reranker import rerank
from intent_processor import process_query
from entity_detector import detect_entities
from generator import generate_answer, generate_answer_stream

# ---------------- CONFIG ----------------
CHROMA_PATH = "database"
COLLECTION_NAME = "docuvault"

app = FastAPI(title="DocuVault API")

# Add CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- LOAD MODELS ON STARTUP ----------------
print("Loading embedding model...")
embedding_model = SentenceTransformer(
    "BAAI/bge-small-en",
    local_files_only=True
)

print("Connecting to ChromaDB...")
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

# Ensure collection exists
try:
    collection = chroma_client.get_collection(name=COLLECTION_NAME)
except:
    collection = chroma_client.create_collection(name=COLLECTION_NAME)


# ---------------- TEXT CHUNKER ----------------
def chunk_text(text, max_chars=900, overlap=200):
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) < max_chars:
            current_chunk += (" " if current_chunk else "") + para
        else:
            chunks.append(current_chunk.strip())
            # Start the new chunk with the last part of the previous chunk if available
            overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
            # Try to snap to a clean space start
            if " " in overlap_text:
                overlap_text = overlap_text[overlap_text.find(" ")+1:]
            current_chunk = overlap_text + " " + para

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


# ---------------- REQUEST MODEL ----------------
class QueryRequest(BaseModel):
    query: str


# ---------------- HEALTH CHECK ----------------
@app.get("/health")
def health():
    return {"status": "DocuVault backend running"}


# ---------------- DOCUMENTS ENDPOINT ----------------
@app.get("/documents")
def get_documents():
    collection = chroma_client.get_collection(name=COLLECTION_NAME)
    results = collection.get(include=["metadatas"])
    metadatas = results["metadatas"]
    
    documents = {}
    for meta in metadatas:
        doc_id = meta.get("doc_id")
        if doc_id and doc_id not in documents:
            documents[doc_id] = {
                "id": doc_id,
                "filename": meta.get("filename", "Unknown")
            }
            
    return {"documents": list(documents.values())}


# ---------------- INGEST ENDPOINT ----------------
@app.post("/ingest")
async def ingest_pdf(file: UploadFile = File(...)):

    temp_path = f"temp_{file.filename}"

    # Save uploaded file
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    collection = chroma_client.get_collection(name=COLLECTION_NAME)

    doc = fitz.open(temp_path)
    doc_id = str(uuid.uuid4())

    all_chunks = []
    all_metadatas = []
    all_ids = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()

        chunks = chunk_text(text)

        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_metadatas.append({
                "doc_id": doc_id,
                "filename": file.filename,
                "page": page_num + 1
            })
            all_ids.append(f"{doc_id}_{page_num}_{i}")

    # Process in batches to avoid memory overflow
    BATCH_SIZE = 50
    for i in range(0, len(all_chunks), BATCH_SIZE):
        batch_chunks = all_chunks[i:i + BATCH_SIZE]
        batch_metadatas = all_metadatas[i:i + BATCH_SIZE]
        batch_ids = all_ids[i:i + BATCH_SIZE]

        # Embed passages properly for BGE
        embeddings = embedding_model.encode(
            ["passage: " + chunk for chunk in batch_chunks],
            normalize_embeddings=True
        )

        collection.add(
            documents=batch_chunks,
            metadatas=batch_metadatas,
            embeddings=embeddings,
            ids=batch_ids
        )

    # IMPORTANT: Close PDF before deleting (Windows fix)
    doc.close()

    os.remove(temp_path)

    return {
        "status": "Document ingested successfully",
        "doc_id": doc_id,
        "filename": file.filename,
        "pages": len(doc),
        "chunks": len(all_chunks)
    }


# ---------------- QUERY ENDPOINT ----------------
@app.post("/query")
def query_doc(request: QueryRequest):

    query = request.query
    expanded_query = process_query(query)

    collection = chroma_client.get_collection(name=COLLECTION_NAME)

    query_embedding = embedding_model.encode(
        "query: " + expanded_query,
        normalize_embeddings=True
    )

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=10
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    reranked = rerank(expanded_query, documents, metadatas, top_k=12)

    contexts = []
    seen_texts = set()
    for doc, meta, score in reranked:
        if doc not in seen_texts:
            contexts.append(doc)
            seen_texts.add(doc)

    pages = list(set([meta["page"] for doc, meta, score in reranked]))

    found_entities = {"emails": [], "phones": [], "urls": []}
    for doc_text, meta, score in reranked:
        entities = detect_entities(doc_text)
        found_entities["emails"].extend(entities["emails"])
        found_entities["phones"].extend(entities["phones"])
        found_entities["urls"].extend(entities["urls"])
        
    # Deduplicate entities
    found_entities = {k: list(set(v)) for k, v in found_entities.items()}

    answer = generate_answer(query, contexts, pages)

    return {
        "answer": answer,
        "pages": pages,
        "entities": found_entities
    }


# ---------------- STREAMING QUERY ENDPOINT ----------------
@app.post("/query_stream")
def query_doc_stream(request: QueryRequest):
    query = request.query
    
    # Check if there are any documents
    collection = chroma_client.get_collection(name=COLLECTION_NAME)
    has_docs = collection.count() > 0
    if not has_docs:
        def empty_gen():
            yield json.dumps({"type": "chunk", "content": "Please upload a document to the vault first!"}) + "\n"
        return StreamingResponse(empty_gen(), media_type="application/x-ndjson")

    # 1. Expand standard query into intelligent query
    expanded_query = process_query(query)

    # 2. Add an intelligent pre-filter router
    where_filter = None
    try:
        from intent_processor import extract_file_filter
        filter_str = extract_file_filter(query)
        if filter_str:
            where_filter = {"filename": {"$contains": filter_str}}
            print(f"Applying Metadata Filter: {where_filter}")
    except Exception as e:
        print("Filter extraction failed, falling back to global search", e)

    query_embedding = embedding_model.encode(
        "query: " + expanded_query,
        normalize_embeddings=True
    )

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=25,
            where=where_filter
        )
    except Exception as e:
        # Fallback if filter causes error (e.g. no docs matched)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=25
        )

    if not results["documents"] or not results["documents"][0]:
        def empty_res():
             yield json.dumps({"type": "chunk", "content": "No relevant documents found for this query."}) + "\n"
        return StreamingResponse(empty_res(), media_type="application/x-ndjson")

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    ids = results["ids"][0]

    reranked = rerank(expanded_query, documents, metadatas, top_k=12)

    contexts = []
    
    # 3. Context Assemble
    seen_texts = set()
    for doc, meta, score in reranked:
        if doc not in seen_texts:
            contexts.append(doc)
            seen_texts.add(doc)

    pages = list(set([meta["page"] for doc, meta, score in reranked]))
    
    # Create source-aware context strings (deduplicated)
    source_contexts = []
    seen_source = set()
    for doc, meta, score in reranked:
        if doc not in seen_source:
            source_contexts.append(f"[Source File: {meta.get('filename', 'Unknown')} | Page: {meta['page']}]\n{doc}")
            seen_source.add(doc)

    found_entities = {"emails": [], "phones": [], "urls": []}
    for doc_text, meta, score in reranked:
        entities = detect_entities(doc_text)
        found_entities["emails"].extend(entities["emails"])
        found_entities["phones"].extend(entities["phones"])
        found_entities["urls"].extend(entities["urls"])
        
    found_entities = {k: list(set(v)) for k, v in found_entities.items()}

    def response_generator():
        # First yield the metadata so the frontend has pages and entities
        metadata = {
            "type": "metadata",
            "pages": pages,
            "entities": found_entities
        }
        yield json.dumps(metadata) + "\n"
        
        # Then stream the text chunks using the source-aware context
        try:
            for chunk in generate_answer_stream(query, source_contexts, pages):
                yield json.dumps({"type": "chunk", "content": chunk}) + "\n"
        except Exception as e:
            error_msg = f"\n\n**Ollama Connection Error:**\n`{str(e)}`\n\nPlease verify that Ollama is running (`ollama serve`) and the `llama3` model is installed (`ollama run llama3`)."
            yield json.dumps({"type": "chunk", "content": error_msg}) + "\n"

    return StreamingResponse(response_generator(), media_type="application/x-ndjson")