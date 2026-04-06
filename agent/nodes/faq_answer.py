"""
FAQ answer node.

Retrieves relevant documents from Pinecone knowledge base (RAG),
then uses LLM to generate a grounded answer. Handles edge cases
(auth refusal, third-party inquiry, meta questions, etc.) via
LLM instructions — no hardcoded keyword matching.
"""

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

from agent.state import AgentState
from agent.prompts.loader import load_system_prompt, get_latest_version
from agent.logging_config import get_logger
from agent.nodes.utils import mark_completed
from rag.retriever import search, format_context

logger = get_logger(__name__)

_llm = ChatOpenAI(model="gpt-4o", temperature=0)

RELEVANCE_THRESHOLD = 0.3

RAG_SYSTEM_PROMPT = """You are a government citizen services voice assistant named Umut.
Your response will be READ ALOUD by a text-to-speech system.

CRITICAL FORMATTING RULES (your text goes directly to TTS):
- Never use tables, bullet points, markdown, numbered lists, or any formatting.
- Never use digits — write ALL numbers as words: "sekiz" not "8", "bes bin" not "5000".
- Never use time formats like "08:00" — write "sabah sekiz" or "aksam bes".
- Never use date formats like "15/03" — write "on bes mart".
- Never use currency with digits like "5.750 TL" — write "bes bin yedi yuz elli lira".
- Maximum 3 sentences. Short and natural, like speaking on the phone.
- Summarize, don't list exhaustively.

ANSWERING QUESTIONS:
- If context documents are provided, answer based ONLY on them. Do not make up information.
- Do NOT add details not explicitly in the context.
- Do NOT suggest visiting websites, calling other numbers, or checking external sources. You ARE the official source.
- When citing the source, say something like "pasaport bilgilerimize gore" or "kayitlarimiza gore" — never say "web sitesini ziyaret edin".
- If the context does not contain the answer, say you don't have that information and offer to help with something else.

EDGE CASE HANDLING (respond naturally, no need for documents):
- Identity refusal ("kimliğimi vermek istemiyorum"): Say you cannot access personal info without verification, but offer to help with general questions. Do NOT push or insist on ID.
- Third-party inquiry ("arkadaşımın başvurusu"): Explain that for security, you can only verify the caller's own identity. The other person needs to call directly. Never share anyone else's data.
- Partial ID ("sonu 901 ile bitiyor"): Explain you need the full 11-digit TC Kimlik number. Mention it's on the front of their ID card.
- Robot/AI question ("sen robot musun?"): Introduce yourself honestly as Umut, an AI-powered voice assistant. Offer to connect with a human if they prefer.
- Previous call reference ("geçen aradığımda"): Explain you don't have access to previous call records. Offer to help with their current need.
- Capability question ("ne yapabilirsin?"): Briefly list what you can help with: application status, appointments, document requests, general info, complaints.
- Anger/profanity: Acknowledge their frustration calmly. Offer to transfer to a human operator immediately.
- Vague date ("doksanlı yıllar"): Ask for exact day, month, and year.

RULES:
- Do NOT suggest transferring to a human operator unless the user explicitly asks or is clearly frustrated.
- Respond in {language_name}.

{context_section}"""

NO_RESULTS_TR = ("Bu konuda bilgi tabanimizda yeterli bilgi bulamadim. "
                 "Baska bir konuda yardimci olabilir miyim?")

NO_RESULTS_EN = ("I couldn't find sufficient information about this in our knowledge base. "
                 "Is there anything else I can help you with?")


def faq_answer(state: AgentState) -> dict:
    """Answer a question using RAG + LLM with edge case handling."""
    language = state.get("language", "tr")
    messages = state.get("messages", [])

    # Extract the latest user question
    user_query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) or getattr(msg, "type", "") == "human":
            user_query = msg.content
            break

    if not user_query:
        user_query = "general information"

    # Step 1: Retrieve from Pinecone
    results = search(query=user_query, language=language, top_k=5)

    # Step 2: Build context section
    if results and results[0].score >= RELEVANCE_THRESHOLD:
        context = format_context(results)
        context_section = f"Context documents:\n{context}"
        source_categories = set(r.category for r in results)
        logger.info(f"FAQ (RAG) | language={language} | sources={source_categories} | top_score={results[0].score:.3f}")
    else:
        context_section = "No relevant documents found. Handle based on edge case rules above, or say you don't have the information."
        logger.info(f"FAQ (no RAG match) | language={language} | query='{user_query[:50]}'")

    # Step 3: Generate response
    language_name = "English" if language == "en" else "Turkish"
    system_prompt = RAG_SYSTEM_PROMPT.format(
        language_name=language_name,
        context_section=context_section,
    )

    response = _llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_query),
    ])

    return {
        "messages": [response],
        "completed_intents": mark_completed(state, state.get("current_intent", "faq")),
    }
