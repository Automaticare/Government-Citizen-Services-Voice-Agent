"""
RAG retriever — queries Pinecone for relevant knowledge base chunks.

Used by LangGraph nodes (faq_answer, status_check) to ground
responses in actual documents rather than LLM hallucination.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from pinecone import Pinecone

from agent.logging_config import get_logger

logger = get_logger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "gov-citizen-services")


@dataclass
class RetrievalResult:
    """A single retrieval result with text and metadata."""
    text: str
    category: str
    doc_type: str
    title: str
    score: float


def _get_clients():
    """Initialize Pinecone and OpenAI clients."""
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    openai_client = OpenAI()
    return pc, openai_client


def search(
    query: str,
    language: str = "tr",
    category: str | None = None,
    top_k: int = 3,
) -> list[RetrievalResult]:
    """Search the knowledge base for relevant chunks.

    Args:
        query: User's question or search term.
        language: Filter results by language ("tr" or "en").
        category: Optional category filter (passport, civil_registry, etc.).
        top_k: Number of results to return.

    Returns:
        List of RetrievalResult ordered by relevance score.
    """
    pc, openai_client = _get_clients()

    # Embed the query
    response = openai_client.embeddings.create(
        input=[query],
        model=EMBEDDING_MODEL,
    )
    query_vector = response.data[0].embedding

    # Build metadata filter
    filters = {"language": language}
    if category:
        filters["category"] = category

    # Query Pinecone
    index = pc.Index(INDEX_NAME)
    results = index.query(
        vector=query_vector,
        top_k=top_k,
        filter=filters,
        include_metadata=True,
    )

    retrieval_results = []
    for match in results.matches:
        retrieval_results.append(RetrievalResult(
            text=match.metadata.get("text", ""),
            category=match.metadata.get("category", ""),
            doc_type=match.metadata.get("doc_type", ""),
            title=match.metadata.get("title", ""),
            score=match.score,
        ))

    logger.info(
        f"RAG search | query='{query[:50]}' | lang={language} | "
        f"results={len(retrieval_results)} | top_score={retrieval_results[0].score:.3f}"
        if retrieval_results else
        f"RAG search | query='{query[:50]}' | lang={language} | results=0"
    )

    return retrieval_results


def format_context(results: list[RetrievalResult]) -> str:
    """Format retrieval results as context string for LLM prompt.

    Includes source attribution so the agent can reference where
    the information came from.
    """
    if not results:
        return ""

    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"[Source {i}: {r.title} ({r.category})]")
        parts.append(r.text)
        parts.append("")

    return "\n".join(parts)


def format_context_tts(results: list[RetrievalResult]) -> str:
    """Format retrieval results for TTS output — no source tags, no formatting.

    Used by service nodes where the response is read aloud.
    Strips markdown, bullet points, and technical formatting.
    """
    if not results:
        return ""

    import re
    parts = []
    for r in results:
        text = r.text
        # Strip markdown headers
        text = re.sub(r'#{1,4}\s+', '', text)
        # Strip bullet points and list markers
        text = re.sub(r'^[\-\*]\s+', '', text, flags=re.MULTILINE)
        # Strip numbered lists
        text = re.sub(r'^\d+[\.\)]\s+', '', text, flags=re.MULTILINE)
        # Replace newlines with spaces
        text = re.sub(r'\n+', ' ', text)
        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        if text:
            parts.append(text)

    return " ".join(parts)
