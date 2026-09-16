"""
Reusable connection clients for Postgres, Qdrant, and MinIO.
Import these from route files instead of creating connections inline.
"""

import os

import psycopg2
from minio import Minio
from qdrant_client import QdrantClient


def get_pg_connection():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        host=os.environ.get("QDRANT_HOST", "localhost"),
        port=int(os.environ.get("QDRANT_PORT", 6333)),
    )


def get_minio_client() -> Minio:
    return Minio(
        f"{os.environ.get('MINIO_HOST', 'localhost')}:{os.environ.get('MINIO_API_PORT', 9000)}",
        access_key=os.environ["MINIO_ROOT_USER"],
        secret_key=os.environ["MINIO_ROOT_PASSWORD"],
        secure=False,
    )
