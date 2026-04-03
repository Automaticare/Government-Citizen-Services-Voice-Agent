"""
Document chunker for RAG pipeline.

Reads markdown documents from the knowledge base and splits them
into overlapping chunks suitable for embedding and retrieval.

Strategy: split by markdown headers (##) first, then by size if
a section is too long. This preserves semantic boundaries — a chunk
about "passport fees" stays together rather than being split mid-sentence.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from agent.logging_config import get_logger

logger = get_logger(__name__)

KB_DIR = Path(__file__).parent.parent / "data" / "knowledge_base"
MANIFEST_PATH = KB_DIR / "manifest.json"

# Chunking parameters
MAX_CHUNK_SIZE = 800   # characters — fits ~200 tokens, good for embedding
CHUNK_OVERLAP = 100    # characters overlap between chunks


@dataclass
class Chunk:
    """A single chunk of text with metadata for Pinecone."""
    id: str
    text: str
    metadata: dict


def load_manifest() -> list[dict]:
    """Load the document manifest."""
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


def _split_by_headers(text: str) -> list[str]:
    """Split markdown text by ## headers, keeping header with content."""
    sections = []
    current = []

    for line in text.split("\n"):
        if line.startswith("## ") and current:
            sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)

    if current:
        sections.append("\n".join(current).strip())

    return [s for s in sections if s]


def _split_by_size(text: str, max_size: int = MAX_CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks by character count."""
    if len(text) <= max_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_size

        # Try to break at a sentence boundary
        if end < len(text):
            last_period = text.rfind(".", start, end)
            last_newline = text.rfind("\n", start, end)
            break_at = max(last_period, last_newline)
            if break_at > start:
                end = break_at + 1

        chunks.append(text[start:end].strip())
        start = end - overlap

    return [c for c in chunks if c]


def chunk_document(doc_meta: dict) -> list[Chunk]:
    """Chunk a single document into retrievable pieces.

    Strategy:
    1. Split by ## headers (semantic boundaries)
    2. If a section exceeds MAX_CHUNK_SIZE, split by size with overlap
    """
    doc_path = KB_DIR / doc_meta["path"]

    if not doc_path.exists():
        logger.warning(f"Document not found: {doc_path}")
        return []

    text = doc_path.read_text(encoding="utf-8")
    title = doc_meta.get("title", "")

    # Split by headers first
    sections = _split_by_headers(text)

    chunks = []
    for i, section in enumerate(sections):
        # Split large sections by size
        sub_chunks = _split_by_size(section)

        for j, chunk_text in enumerate(sub_chunks):
            chunk_id = f"{doc_meta['id']}_chunk_{i}_{j}"
            chunks.append(Chunk(
                id=chunk_id,
                text=chunk_text,
                metadata={
                    "doc_id": doc_meta["id"],
                    "category": doc_meta["category"],
                    "language": doc_meta["language"],
                    "doc_type": doc_meta["doc_type"],
                    "title": title,
                    "chunk_index": i,
                },
            ))

    return chunks


def chunk_all_documents() -> list[Chunk]:
    """Chunk all documents in the knowledge base."""
    manifest = load_manifest()
    all_chunks = []

    for doc in manifest:
        chunks = chunk_document(doc)
        all_chunks.extend(chunks)

    logger.info(f"Chunked {len(manifest)} documents into {len(all_chunks)} chunks")
    return all_chunks
