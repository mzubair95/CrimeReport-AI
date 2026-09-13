"""
Developer script to (re)build the knowledge-base index in Pinecone.

Usage:
    python -m rag.ingest

Walks knowledge_base/{crimes,procedures,authorities}/*.{txt,md,pdf,docx},
extracts text, chunks it, embeds each chunk, and upserts into Pinecone with
metadata (source file, category, chunk text) so the retriever can cite it.

knowledge_base/legal/ is handled separately (see ingest_legal()) — it's a
structured JSON file of statute citations, not freeform prose, and is
upserted into its own "legal" Pinecone namespace so a legal-reference lookup
can never accidentally surface general reporting-guidance text instead of an
actual citation (docs/FIR_TECHNICAL_SPEC.md §3.2).
"""
from __future__ import annotations

import hashlib
import json
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

LEGAL_NAMESPACE = "legal"
LEGAL_KB_FILE = KB_DIR / "legal" / "legal_references.json"


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
        if not category_dir.is_dir() or category_dir.name == "legal":
            continue  # legal/ is structured JSON, ingested separately (ingest_legal)
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


def ingest_legal(batch_size: int = 50) -> int:
    """
    Ingest knowledge_base/legal/legal_references.json — one vector per
    structured statute record, embedded from its category/statute/section/
    summary, and upserted into the "legal" namespace with the full record
    (including the UNVERIFIED-draft fields) preserved as metadata so
    ai/legal_service.py can return exact structured fields rather than
    re-parsing prose.
    """
    if not is_available():
        logger.error("Pinecone is not configured/available. Set PINECONE_API_KEY "
                      "and PINECONE_INDEX in .env before running ingestion.")
        return 0
    if not LEGAL_KB_FILE.exists():
        logger.warning("No legal knowledge base found at %s", LEGAL_KB_FILE)
        return 0

    records = json.loads(LEGAL_KB_FILE.read_text(encoding="utf-8"))
    texts = [
        f"{r['category']} — {r['statute']} Section {r['section_number']}: "
        f"{r['section_title']}. {r['summary']}"
        for r in records
    ]
    embeddings = embed_texts(texts)

    vectors_batch = []
    total = 0
    for i, (record, vector) in enumerate(zip(records, embeddings)):
        vec_id = hashlib.sha1(f"legal-{record['statute']}-{record['section_number']}-{i}"
                               .encode()).hexdigest()
        vectors_batch.append({"id": vec_id, "values": vector, "metadata": record})
        total += 1
        if len(vectors_batch) >= batch_size:
            upsert_vectors(vectors_batch, namespace=LEGAL_NAMESPACE)
            vectors_batch = []

    if vectors_batch:
        upsert_vectors(vectors_batch, namespace=LEGAL_NAMESPACE)

    logger.info("Legal ingestion complete: %d record(s) upserted into namespace '%s'.",
                total, LEGAL_NAMESPACE)
    return total


if __name__ == "__main__":
    count = ingest_all()
    legal_count = ingest_legal()
    sys.exit(0 if (count > 0 or legal_count > 0) else 1)
