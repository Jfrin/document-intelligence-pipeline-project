"""
Query pipeline: embed a question, search Qdrant for the closest chunks,
and optionally ask an LLM to synthesize an answer from them.

LLM generation is optional and only runs if ANTHROPIC_API_KEY is set in
.env — without it, /query still works and just returns the raw matched
chunks (bare semantic search, no generation).
"""

import os

from processing import COLLECTION_NAME, get_embedding_model
from clients import get_qdrant_client


def search_chunks(question: str, top_k: int = 5) -> list[dict]:
    model = get_embedding_model()
    query_vector = model.encode(question).tolist()

    client = get_qdrant_client()
    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k,
    )

    return [
        {
            "score": r.score,
            "text": r.payload.get("text"),
            "filename": r.payload.get("filename"),
            "document_id": r.payload.get("document_id"),
            "chunk_index": r.payload.get("chunk_index"),
        }
        for r in results
    ]


def generate_answer(question: str, chunks: list[dict]) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not chunks:
        return None

    import anthropic

    context = "\n\n".join(f"[{c['filename']} chunk {c['chunk_index']}]\n{c['text']}" for c in chunks)
    prompt = (
        "Answer the question using only the context below. "
        "If the context doesn't contain the answer, say so.\n\n"
        f"Context:\n{context}\n\nQuestion: {question}"
    )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def answer_question(question: str, top_k: int = 5) -> dict:
    chunks = search_chunks(question, top_k=top_k)
    answer = generate_answer(question, chunks)
    return {"question": question, "answer": answer, "sources": chunks}
