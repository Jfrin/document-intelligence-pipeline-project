"""
document-intelligence-pipeline backend — step 1 scaffold.

Just a FastAPI app with a health-check route that confirms it can reach
Postgres, Qdrant, and MinIO. No business logic yet — that comes in later steps.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

# Load the .env that lives at the project root (one level up from backend/)
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

app = FastAPI(title="Document Intelligence Pipeline — backend")


def check_postgres() -> str:
    try:
        import psycopg2

        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            connect_timeout=3,
        )
        conn.close()
        return "ok"
    except Exception as e:
        return f"error: {e}"


def check_qdrant() -> str:
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(host="localhost", port=int(os.environ.get("QDRANT_PORT", 6333)))
        client.get_collections()
        return "ok"
    except Exception as e:
        return f"error: {e}"


def check_minio() -> str:
    try:
        from minio import Minio

        client = Minio(
            f"localhost:{os.environ.get('MINIO_API_PORT', 9000)}",
            access_key=os.environ["MINIO_ROOT_USER"],
            secret_key=os.environ["MINIO_ROOT_PASSWORD"],
            secure=False,
        )
        client.list_buckets()
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
