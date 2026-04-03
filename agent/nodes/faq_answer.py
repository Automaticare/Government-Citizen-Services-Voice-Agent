"""
FAQ answer node.

Retrieves relevant documents from Pinecone knowledge base (RAG),
then uses LLM to generate a grounded answer. Agent cites the source
and refuses to answer beyond what the documents contain.
"""

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from agent.state import AgentState
from agent.prompts.loader import load_system_prompt, get_latest_version
from agent.logging_config import get_logger
from agent.nodes.utils import mark_completed
from rag.retriever import search, format_context

logger = get_logger(__name__)

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

# Below this score, retrieval is considered irrelevant
RELEVANCE_THRESHOLD = 0.3

RAG_SYSTEM_PROMPT = """You are a government citizen services assistant named Umut.
Answer the user's question based ONLY on the provided context documents.

Rules:
- Only use information from the provided context. Do not make up information.
- If the context does not contain the answer, say so honestly and offer to connect with a human operator.
- Mention the source category when answering (e.g., "According to our passport services information...").
- Be concise and helpful.
- Respond in {language_name}.

Context documents:
{context}"""

NO_RESULTS_TR = ("Bu konuda bilgi tabanımızda yeterli bilgi bulamadım. "
                 "Dilerseniz sizi daha detaylı yardımcı olabilecek bir operatöre bağlayabilirim. "
                 "Başka bir konuda yardımcı olabilir miyim?")

NO_RESULTS_EN = ("I couldn't find sufficient information about this in our knowledge base. "
                 "I can connect you with a human operator for more detailed assistance. "
                 "Is there anything else I can help you with?")


def faq_answer(state: AgentState) -> dict:
    """Answer a question using RAG — retrieve from Pinecone, then generate grounded response."""
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

    # Step 1: Retrieve from Pinecone (top_k=5 for better coverage across doc types)
    results = search(query=user_query, language=language, top_k=5)

    # Step 2: Check relevance
    if not results or results[0].score < RELEVANCE_THRESHOLD:
        logger.info(f"FAQ — no relevant results | query='{user_query[:50]}' | language={language}")
        no_result_msg = NO_RESULTS_EN if language == "en" else NO_RESULTS_TR
        from langchain_core.messages import AIMessage
        return {
            "messages": [AIMessage(content=no_result_msg)],
            "completed_intents": mark_completed(state, state.get("current_intent", "faq")),
        }

    # Step 3: Build grounded prompt with retrieved context
    context = format_context(results)
    language_name = "English" if language == "en" else "Turkish"

    system_prompt = RAG_SYSTEM_PROMPT.format(
        language_name=language_name,
        context=context,
    )

    response = _llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_query),
    ])

    source_categories = set(r.category for r in results)
    logger.info(f"FAQ answered (RAG) | language={language} | sources={source_categories} | top_score={results[0].score:.3f}")

    return {
        "messages": [response],
        "completed_intents": mark_completed(state, state.get("current_intent", "faq")),
    }
