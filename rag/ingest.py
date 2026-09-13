"""
Developer script to (re)build the knowledge-base index in Pinecone.

Usage:
    python -m rag.ingest

Walks knowledge_base/{crimes,procedures,authorities}/*.{txt,md,pdf,docx},
extracts text, chunks it, embeds each chunk, and upserts into Pinecone with
metadata (source file, category, chunk text) so the retriever can cite it.
"""
from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path

from config.settings import BASE_DIR
from rag.embeddings import embed_texts
from rag.pinecone_client import upsert_vectors, is_available

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("crime_report_ai.ingest")

KB_DIR = BASE_DIR / "knowledge_base"
CHUNK_SIZE = 800     # characters per chunk — small chunks keep Pinecone usage cheap
CHUNK_OVERLAP = 120


def load_text(path: Path) -> str:
    suffix = path.suffix.lower()
    try:
        if suffix in (".txt", ".md"):
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        if suffix == ".docx":
            from docx import Document
            doc = Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs)
    except Exception as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return ""
    logger.warning("Unsupported file type, skipping: %s", path)
    return ""


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = " ".join(text.split())  # normalize whitespace
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def iter_documents():
    for category_dir in KB_DIR.iterdir():
        if not category_dir.is_dir():
            continue
        category = category_dir.name  # "crimes" / "procedures" / "authorities"
        for path in category_dir.glob("*"):
            if path.is_file():
                yield category, path


def ingest_all(batch_size: int = 50) -> int:
    if not is_available():
        logger.error("Pinecone is not configured/available. Set PINECONE_API_KEY "
                      "and PINECONE_INDEX in .env before running ingestion.")
        return 0

    vectors_batch = []
    total_chunks = 0

    for category, path in iter_documents():
        text = load_text(path)
        chunks = chunk_text(text)
        if not chunks:
            continue
        logger.info("Chunked %s into %d piece(s)", path.name, len(chunks))
        embeddings = embed_texts(chunks)
        for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            vec_id = hashlib.sha1(f"{path.name}-{i}".encode()).hexdigest()
            vectors_batch.append({
                "id": vec_id,
                "values": vector,
                "metadata": {
                    "text": chunk,
                    "category": category,
                    "source": path.name,
                    "chunk_index": i,
                },
            })
            total_chunks += 1
            if len(vectors_batch) >= batch_size:
                upsert_vectors(vectors_batch)
                vectors_batch = []

    if vectors_batch:
        upsert_vectors(vectors_batch)

    logger.info("Ingestion complete: %d chunk(s) upserted.", total_chunks)
    return total_chunks


if __name__ == "__main__":
    count = ingest_all()
    sys.exit(0 if count > 0 else 1)
