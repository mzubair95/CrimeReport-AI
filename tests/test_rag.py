"""
Tests for the RAG pipeline's offline-safe pieces: chunking always works
without any API keys; retrieval/embedding are only exercised live if
PINECONE_API_KEY is configured (skipped otherwise so CI doesn't need secrets).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.ingest import chunk_text
from rag import pinecone_client


def test_chunk_text_basic():
    text = "word " * 500
    chunks = chunk_text(text, size=100, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)


def test_chunk_text_empty():
    assert chunk_text("") == []


def test_retrieval_skips_without_pinecone():
    from rag.retriever import retrieve_context
    if pinecone_client.is_available():
        result = retrieve_context("stolen phone from car")
        assert isinstance(result, str)
    else:
        # Must degrade gracefully, never raise, when Pinecone isn't configured.
        assert retrieve_context("stolen phone from car") == ""


if __name__ == "__main__":
    test_chunk_text_basic()
    test_chunk_text_empty()
    test_retrieval_skips_without_pinecone()
    print("RAG tests passed.")
