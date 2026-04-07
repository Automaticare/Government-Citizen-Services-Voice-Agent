"""
Embedding pipeline for ElevenLabs documentation.

Chunks ElevenLabs docs and upserts to a separate Pinecone index.
Used by the LLM recommendation engine to provide platform-aware
optimization suggestions.

Usage:
    python -m rag.embed_elevenlabs              # Embed all docs
    python -m rag.embed_elevenlabs --reset      # Delete and re-embed
    python -m rag.embed_elevenlabs --validate   # Run test queries
"""

import argparse
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

from agent.logging_config import get_logger

logger = get_logger(__name__)

DOCS_DIR = Path(__file__).parent.parent / "elevenlabs_documentations"
INDEX_NAME = os.getenv("PINECONE_ELEVENLABS_INDEX", "elevenlabs-docs")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
BATCH_SIZE = 50
MAX_CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
MIN_CHUNK_SIZE = 50


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict


def _chunk_markdown(text: str, doc_name: str) -> list[Chunk]:
    """Split markdown by headers, then by size."""
    sections = re.split(r'\n(?=##\s)', text)
    chunks = []

    for i, section in enumerate(sections):
        section = section.strip()
        if len(section) < MIN_CHUNK_SIZE:
            continue

        if len(section) <= MAX_CHUNK_SIZE:
            chunks.append(Chunk(
                id=f"el-{doc_name}-{i}",
                text=section,
                metadata={"source": doc_name, "category": "elevenlabs_docs"},
            ))
        else:
            # Split by paragraphs
            paragraphs = section.split("\n\n")
            current = ""
            chunk_idx = 0
            for para in paragraphs:
                if len(current) + len(para) > MAX_CHUNK_SIZE and current:
                    chunks.append(Chunk(
                        id=f"el-{doc_name}-{i}-{chunk_idx}",
                        text=current.strip(),
                        metadata={"source": doc_name, "category": "elevenlabs_docs"},
                    ))
                    # Overlap
                    current = current[-CHUNK_OVERLAP:] + "\n\n" + para
                    chunk_idx += 1
                else:
                    current += "\n\n" + para if current else para

            if current.strip() and len(current.strip()) >= MIN_CHUNK_SIZE:
                chunks.append(Chunk(
                    id=f"el-{doc_name}-{i}-{chunk_idx}",
                    text=current.strip(),
                    metadata={"source": doc_name, "category": "elevenlabs_docs"},
                ))

    return chunks


def chunk_all_docs() -> list[Chunk]:
    """Chunk all ElevenLabs documentation files."""
    all_chunks = []

    for md_file in sorted(DOCS_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        doc_name = md_file.stem
        chunks = _chunk_markdown(text, doc_name)
        all_chunks.extend(chunks)
        logger.info(f"Chunked {doc_name}: {len(chunks)} chunks")

    logger.info(f"Total chunks: {len(all_chunks)} from {len(list(DOCS_DIR.glob('*.md')))} files")
    return all_chunks


def run(reset: bool = False, validate_after: bool = False):
    """Full pipeline: chunk → embed → upsert."""
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise ValueError("PINECONE_API_KEY not set")

    pc = Pinecone(api_key=api_key)
    openai_client = OpenAI()

    # Ensure index
    existing = [idx.name for idx in pc.list_indexes()]
    if reset and INDEX_NAME in existing:
        logger.info(f"Deleting index: {INDEX_NAME}")
        pc.delete_index(INDEX_NAME)
        time.sleep(5)
        existing = []

    if INDEX_NAME not in existing:
        logger.info(f"Creating index: {INDEX_NAME}")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIMENSIONS,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        while not pc.describe_index(INDEX_NAME).status.get("ready", False):
            logger.info("Waiting for index...")
            time.sleep(2)

    # Chunk
    chunks = chunk_all_docs()

    # Embed
    vectors = []
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        texts = [c.text for c in batch]
        response = openai_client.embeddings.create(input=texts, model=EMBEDDING_MODEL)
        for chunk, emb in zip(batch, response.data):
            vectors.append((chunk.id, emb.embedding, {**chunk.metadata, "text": chunk.text}))
        logger.info(f"Embedded {len(vectors)}/{len(chunks)}")

    # Upsert
    index = pc.Index(INDEX_NAME)
    for i in range(0, len(vectors), BATCH_SIZE):
        index.upsert(vectors=vectors[i:i + BATCH_SIZE])
    logger.info(f"Upserted {len(vectors)} vectors")

    # Validate
    if validate_after:
        test_queries = [
            "How to integrate custom LLM with ElevenLabs",
            "Workflow edge conditions and transitions",
            "Dynamic variables in system prompt",
            "Twilio phone integration setup",
            "Authentication flow design for voice agents",
        ]
        for q in test_queries:
            resp = openai_client.embeddings.create(input=[q], model=EMBEDDING_MODEL)
            results = index.query(vector=resp.data[0].embedding, top_k=2, include_metadata=True)
            if results.matches:
                top = results.matches[0]
                print(f"  [{top.score:.3f}] '{q[:50]}' -> {top.metadata.get('source', '?')}")
            else:
                print(f"  [FAIL] '{q[:50]}' -> no results")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Embed ElevenLabs docs into Pinecone")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    run(reset=args.reset, validate_after=args.validate)
