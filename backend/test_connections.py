"""
Standalone test: proves each service can actually be written to and read
from, not just connected to. Run this once after `docker compose up`.

Usage (from inside the backend container or a local venv with the same env):
    python test_connections.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

from clients import get_minio_client, get_pg_connection, get_qdrant_client  # noqa: E402


def test_postgres():
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS _connection_test (id SERIAL PRIMARY KEY, note TEXT);")
    cur.execute("INSERT INTO _connection_test (note) VALUES ('hello from test_connections.py');")
    cur.execute("SELECT COUNT(*) FROM _connection_test;")
    count = cur.fetchone()[0]
    cur.execute("DROP TABLE _connection_test;")
    conn.commit()
    cur.close()
    conn.close()
    print(f"[postgres] wrote + read + dropped a test table OK (row count was {count})")


def test_qdrant():
    from qdrant_client.models import Distance, VectorParams

    client = get_qdrant_client()
    if client.collection_exists("_connection_test"):
        client.delete_collection("_connection_test")
    client.create_collection(
        collection_name="_connection_test",
        vectors_config=VectorParams(size=4, distance=Distance.COSINE),
    )
    client.upsert(
        collection_name="_connection_test",
        points=[{"id": 1, "vector": [0.1, 0.2, 0.3, 0.4], "payload": {"note": "test"}}],
    )
    results = client.count(collection_name="_connection_test").count
    client.delete_collection("_connection_test")
    print(f"[qdrant] created collection + upserted + counted + deleted OK (count was {results})")


def test_minio():
    client = get_minio_client()
    bucket = "connection-test-bucket"
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    import io

    data = b"hello from test_connections.py"
    client.put_object(bucket, "test.txt", io.BytesIO(data), length=len(data))
    obj = client.get_object(bucket, "test.txt")
    content = obj.read()
    client.remove_object(bucket, "test.txt")
    client.remove_bucket(bucket)
    print(f"[minio] created bucket + wrote + read + deleted OK (content: {content.decode()!r})")


if __name__ == "__main__":
    test_postgres()
    test_qdrant()
    test_minio()
    print("\nAll three services passed real read/write tests.")
