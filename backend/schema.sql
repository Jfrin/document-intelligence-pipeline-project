-- Documents table: tracks every file uploaded to the pipeline and its
-- processing status through the extract -> chunk -> embed pipeline.

CREATE TABLE IF NOT EXISTS documents (
    id              SERIAL PRIMARY KEY,
    filename        TEXT NOT NULL,
    minio_object    TEXT NOT NULL,          -- object name/key inside the MinIO bucket
    status          TEXT NOT NULL DEFAULT 'uploaded',  -- uploaded | processing | ready | error
    error_message   TEXT,
    chunk_count     INTEGER DEFAULT 0,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_documents_status ON documents (status);
