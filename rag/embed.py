"""
Embedding pipeline for RAG.

Reads chunked documents, generates embeddings via OpenAI, and
upserts to Pinecone. Handles batching for API rate limits.

Usage:
    python -m rag.embed              # Embed and upsert all documents
    python -m rag.embed --validate   # Run validation queries after upsert
    python -m rag.embed --reset      # Delete index and re-embed everything
"""

import argparse
import os
import time

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

from agent.logging_config import get_logger
from rag.chunker import chunk_all_documents, Chunk

logger = get_logger(__name__)

# Config
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "gov-citizen-services")
PINECONE_CLOUD = "aws"
PINECONE_REGION = "us-east-1"
BATCH_SIZE = 50  # vectors per upsert batch


def _get_pinecone():
    """Initialize Pinecone client."""
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise ValueError("PINECONE_API_KEY not set in .env")
    return Pinecone(api_key=api_key)


def _get_openai():
    """Initialize OpenAI client."""
    return OpenAI()


def ensure_index(pc: Pinecone, reset: bool = False) -> None:
    """Create Pinecone index if it doesn't exist."""
    existing = [idx.name for idx in pc.list_indexes()]

    if reset and INDEX_NAME in existing:
        logger.info(f"Deleting existing index: {INDEX_NAME}")
        pc.delete_index(INDEX_NAME)
        time.sleep(5)  # Wait for deletion
        existing = []

    if INDEX_NAME not in existing:
        logger.info(f"Creating index: {INDEX_NAME} (dim={EMBEDDING_DIMENSIONS})")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIMENSIONS,
            metric="cosine",
            spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
        )
        # Wait for index to be ready
        while not pc.describe_index(INDEX_NAME).status.get("ready", False):
            logger.info("Waiting for index to be ready...")
            time.sleep(2)

    logger.info(f"Index ready: {INDEX_NAME}")


def embed_chunks(openai_client: OpenAI, chunks: list[Chunk]) -> list[tuple[str, list[float], dict]]:
    """Generate embeddings for chunks and return (id, vector, metadata) tuples."""
    vectors = []

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        texts = [c.text for c in batch]

        response = openai_client.embeddings.create(
            input=texts,
            model=EMBEDDING_MODEL,
        )

        for chunk, embedding_data in zip(batch, response.data):
            vectors.append((
                chunk.id,
                embedding_data.embedding,
                {**chunk.metadata, "text": chunk.text},  # Store text in metadata for retrieval
            ))

        logger.info(f"Embedded batch {i // BATCH_SIZE + 1} ({len(vectors)}/{len(chunks)} chunks)")

    return vectors


def upsert_vectors(pc: Pinecone, vectors: list[tuple]) -> None:
    """Upsert vectors to Pinecone in batches."""
    index = pc.Index(INDEX_NAME)

    for i in range(0, len(vectors), BATCH_SIZE):
        batch = vectors[i:i + BATCH_SIZE]
        # Pinecone expects list of (id, values, metadata)
        index.upsert(vectors=batch)
        logger.info(f"Upserted batch {i // BATCH_SIZE + 1}")

    stats = index.describe_index_stats()
    logger.info(f"Index stats: {stats.total_vector_count} total vectors")


def validate(pc: Pinecone, openai_client: OpenAI) -> None:
    """Run test queries to verify retrieval quality."""
    index = pc.Index(INDEX_NAME)

    test_queries = [
        ("Pasaport için hangi belgeler gerekli?", "tr", "passport"),
        ("What are the passport fees?", "en", "passport"),
        ("Ehliyet yenileme ücreti ne kadar?", "tr", "drivers_license"),
        ("How to book an appointment?", "en", "appointments"),
        ("Şikayet nasıl yapılır?", "tr", "general"),
    ]

    for query, language, expected_category in test_queries:
        response = openai_client.embeddings.create(
            input=[query],
            model=EMBEDDING_MODEL,
        )
        query_vector = response.data[0].embedding

        results = index.query(
            vector=query_vector,
            top_k=3,
            filter={"language": language},
            include_metadata=True,
        )

        top_match = results.matches[0] if results.matches else None

        if top_match:
            cat = top_match.metadata.get("category", "?")
            score = top_match.score
            status = "PASS" if cat == expected_category else "WARN"
            msg = f"  [{status}] '{query[:40]}...' -> {cat} (score={score:.3f}, expected={expected_category})"
            print(msg.encode("ascii", errors="replace").decode("ascii"))
        else:
            print(f"  [FAIL] '{query[:40]}...' -> no results")


def run(reset: bool = False, validate_after: bool = False, validate_only: bool = False) -> None:
    """Full embedding pipeline: chunk → embed → upsert."""
    pc = _get_pinecone()
    openai_client = _get_openai()

    if validate_only:
        logger.info("Running validation queries only...")
        validate(pc, openai_client)
        return

    # Step 1: Ensure index
    ensure_index(pc, reset=reset)

    # Step 2: Chunk documents
    chunks = chunk_all_documents()
    logger.info(f"Total chunks: {len(chunks)}")

    # Step 3: Embed
    vectors = embed_chunks(openai_client, chunks)

    # Step 4: Upsert to Pinecone
    upsert_vectors(pc, vectors)

    # Step 5: Validate
    if validate_after:
        logger.info("Running validation queries...")
        validate(pc, openai_client)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Embed knowledge base into Pinecone")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate index")
    parser.add_argument("--validate", action="store_true", help="Run validation after upsert")
    parser.add_argument("--validate-only", action="store_true", help="Only run validation queries")
    args = parser.parse_args()

    run(reset=args.reset, validate_after=args.validate, validate_only=args.validate_only)
