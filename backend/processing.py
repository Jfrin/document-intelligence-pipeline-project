"""
Processing pipeline: takes an uploaded document (already in MinIO + Postgres
with status 'uploaded') and turns it into searchable chunks in Qdrant.

Flow: download from MinIO -> extract text -> chunk -> embed -> upsert to
Qdrant -> update the Postgres row to 'ready' (or 'error' if anything fails).
"""

import io
import uuid
from datetime import datetime, timezone
from functools import lru_cache

from qdrant_client.models import Distance, PointStruct, VectorParams

from clients import get_minio_client, get_pg_connection, get_qdrant_client

BUCKET_NAME = "documents"
COLLECTION_NAME = "document_chunks"
CHUNK_SIZE = 500          # characters per chunk
CHUNK_OVERLAP = 50        # characters of overlap between chunks
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384        # matches all-MiniLM-L6-v2's output size


@lru_cache(maxsize=1)
def get_embedding_model():
    # cached so the model only loads once per process, not per request
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def ensure_qdrant_collection():
    client = get_qdrant_client()
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )


def extract_text(filename: str, file_bytes: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        # treat everything else as plain text
        return file_bytes.decode("utf-8", errors="ignore")


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def set_status(doc_id: int, status: str, error_message: str | None = None, chunk_count: int | None = None):
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE documents SET status = %s, error_message = %s, "
        "chunk_count = COALESCE(%s, chunk_count), processed_at = %s WHERE id = %s;",
        (status, error_message, chunk_count, datetime.now(timezone.utc), doc_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def process_document(doc_id: int):
    """Runs as a background task right after upload. Safe to call standalone too."""
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("SELECT filename, minio_object FROM documents WHERE id = %s;", (doc_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row is None:
        return  # doc_id doesn't exist, nothing to do

    filename, minio_object = row

    try:
        set_status(doc_id, "processing")
        ensure_qdrant_collection()

        minio_client = get_minio_client()
        obj = minio_client.get_object(BUCKET_NAME, minio_object)
        file_bytes = obj.read()

        text = extract_text(filename, file_bytes)
        chunks = chunk_text(text)

        if not chunks:
            set_status(doc_id, "error", error_message="No extractable text found.", chunk_count=0)
            return

        model = get_embedding_model()
        embeddings = model.encode(chunks).tolist()

        qdrant_client = get_qdrant_client()
        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}-{i}")),
                vector=embeddings[i],
                payload={"document_id": doc_id, "filename": filename, "chunk_index": i, "text": chunks[i]},
            )
            for i in range(len(chunks))
        ]
        qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)

        set_status(doc_id, "ready", chunk_count=len(chunks))

    except Exception as e:
        set_status(doc_id, "error", error_message=str(e))
