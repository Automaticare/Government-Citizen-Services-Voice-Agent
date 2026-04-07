"""
LLM-powered insight engine for the analytics dashboard.

Analyzes conversation metrics + ElevenLabs docs RAG to generate
actionable, platform-aware optimization recommendations.

Three insight types:
1. RAG Performance — knowledge gaps and content recommendations
2. Node Performance — bottleneck detection and optimization tips
3. Proactive Patterns — escalation/failure pattern analysis
"""

import os
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone

load_dotenv()

ELEVENLABS_INDEX = os.getenv("PINECONE_ELEVENLABS_INDEX", "elevenlabs-docs")
EMBEDDING_MODEL = "text-embedding-3-small"


def _get_platform_context(query: str, top_k: int = 3) -> str:
    """Retrieve relevant ElevenLabs documentation for context."""
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        return ""

    try:
        pc = Pinecone(api_key=api_key)
        openai_client = OpenAI()

        resp = openai_client.embeddings.create(input=[query], model=EMBEDDING_MODEL)
        vector = resp.data[0].embedding

        index = pc.Index(ELEVENLABS_INDEX)
        results = index.query(vector=vector, top_k=top_k, include_metadata=True)

        if results.matches:
            contexts = []
            for m in results.matches:
                source = m.metadata.get("source", "unknown")
                text = m.metadata.get("text", "")[:500]
                contexts.append(f"[{source}]: {text}")
            return "\n\n".join(contexts)
    except Exception:
        pass

    return ""


def generate_insights(df: pd.DataFrame, auth_df: pd.DataFrame = None) -> list[dict]:
    """Generate LLM-powered insights from conversation metrics.

    Returns list of {"type": str, "title": str, "detail": str, "priority": str}
    """
    if df.empty:
        return []

    # Build metrics summary
    total = len(df)
    escalated = (df["intent"] == "escalate").sum()
    escalation_rate = escalated / max(1, total) * 100

    avg_response = df["response_time_ms"].mean() if df["response_time_ms"].notna().any() else 0

    # RAG metrics
    rag_df = df[df["rag_query"].notna() & (df["rag_query"] != "")]
    low_rag = rag_df[rag_df["rag_score"] < 0.4] if not rag_df.empty else pd.DataFrame()

    # Intent distribution
    intent_counts = df["intent"].value_counts().to_dict()

    # Node timing
    classify_avg = df["intent_classify_ms"].mean() if "intent_classify_ms" in df.columns and df["intent_classify_ms"].notna().any() else None

    # Auth metrics
    auth_fail_rate = 0
    if auth_df is not None and not auth_df.empty:
        total_auth = len(auth_df)
        failures = (auth_df["result"] == "failure").sum()
        auth_fail_rate = failures / max(1, total_auth) * 100

    metrics_summary = f"""
CONVERSATION METRICS (last {total} requests):
- Total requests: {total}
- Escalation rate: {escalation_rate:.1f}%
- Avg response time: {avg_response:.0f}ms
- Intent distribution: {intent_counts}
- Intent classify avg: {classify_avg:.0f}ms (if available)
- RAG queries: {len(rag_df)}, low score (<0.4): {len(low_rag)}
- Auth failure rate: {auth_fail_rate:.0f}%
"""

    if not low_rag.empty:
        gap_queries = low_rag["rag_query"].tolist()[:5]
        metrics_summary += f"- Knowledge gap queries: {gap_queries}\n"

    # Get platform context from ElevenLabs docs
    platform_context = _get_platform_context(
        "voice agent optimization latency performance knowledge base workflow"
    )

    # Generate insights via LLM
    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.3,
            messages=[
                {"role": "system", "content": """You are an expert Forward Deployed Engineer analyzing a voice agent system built on ElevenLabs + LangGraph.

Given conversation metrics and ElevenLabs platform documentation, generate 3-5 actionable recommendations.

Each recommendation must be:
- SPECIFIC: reference actual metrics and thresholds
- ACTIONABLE: say exactly what to change
- PLATFORM-AWARE: leverage ElevenLabs features when relevant

Format each as JSON: {"type": "rag|performance|pattern", "title": "short title", "detail": "2-3 sentence recommendation", "priority": "high|medium|low"}

Return a JSON array of recommendations. No markdown, just valid JSON."""},
                {"role": "user", "content": f"""
{metrics_summary}

ELEVENLABS PLATFORM CONTEXT:
{platform_context}

Generate actionable recommendations based on these metrics and platform capabilities."""}
            ],
        )

        import json
        content = response.choices[0].message.content.strip()
        # Handle potential markdown wrapping
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        insights = json.loads(content)
        return insights

    except Exception as e:
        return [{"type": "error", "title": "Insight generation failed", "detail": str(e), "priority": "low"}]
