"""
document-intelligence-pipeline backend.

Endpoints so far:
  GET  /health      - confirms Postgres, Qdrant, MinIO are reachable
  GET  /documents    - list uploaded documents and their status
  POST /upload        - upload a file: stored in MinIO, tracked in Postgres,
                          processed (extract -> chunk -> embed -> Qdrant) in the background
"""

import io
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from pydantic import BaseModel

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

from clients import get_minio_client, get_pg_connection, get_qdrant_client  # noqa: E402
from processing import ensure_qdrant_collection, process_document  # noqa: E402
from query import answer_question  # noqa: E402

BUCKET_NAME = "documents"

app = FastAPI(title="Document Intelligence Pipeline — backend")


def ensure_bucket():
    client = get_minio_client()
    if not client.bucket_exists(BUCKET_NAME):
        client.make_bucket(BUCKET_NAME)


@app.on_event("startup")
def on_startup():
    ensure_bucket()
    ensure_qdrant_collection()


def check_postgres() -> str:
    try:
        conn = get_pg_connection()
        conn.close()
        return "ok"
    except Exception as e:
        return f"error: {e}"


def check_qdrant() -> str:
    try:
        get_qdrant_client().get_collections()
        return "ok"
    except Exception as e:
        return f"error: {e}"


def check_minio() -> str:
    try:
        get_minio_client().list_buckets()
        return "ok"
    except Exception as e:
        return f"error: {e}"


@app.get("/health")
def health():
    return {
        "api": "ok",
        "postgres": check_postgres(),
        "qdrant": check_qdrant(),
        "minio": check_minio(),
    }


@app.get("/")
def root():
    return {"message": "Document Intelligence Pipeline backend is running. See /health and /docs."}


@app.get("/documents")
def list_documents():
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, filename, status, chunk_count, uploaded_at, processed_at, error_message "
        "FROM documents ORDER BY uploaded_at DESC;"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "id": r[0],
            "filename": r[1],
            "status": r[2],
            "chunk_count": r[3],
            "uploaded_at": r[4].isoformat() if r[4] else None,
            "processed_at": r[5].isoformat() if r[5] else None,
            "error_message": r[6],
        }
        for r in rows
    ]


@app.post("/upload")
async def upload_document(file: UploadFile, background_tasks: BackgroundTasks):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    object_name = f"{uuid.uuid4()}-{file.filename}"
    contents = await file.read()

    minio_client = get_minio_client()
    minio_client.put_object(
        BUCKET_NAME,
        object_name,
        io.BytesIO(contents),
        length=len(contents),
        content_type=file.content_type or "application/octet-stream",
    )

    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO documents (filename, minio_object, status) "
        "VALUES (%s, %s, 'uploaded') RETURNING id;",
        (file.filename, object_name),
    )
    doc_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    background_tasks.add_task(process_document, doc_id)

    return {
        "id": doc_id,
        "filename": file.filename,
        "minio_object": object_name,
        "status": "uploaded",
    }


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5


@app.post("/query")
def query(req: QueryRequest):
    return answer_question(req.question, top_k=req.top_k)
