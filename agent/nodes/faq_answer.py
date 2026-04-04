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

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Below this score, retrieval is considered irrelevant
RELEVANCE_THRESHOLD = 0.3

EDGE_CASE_PATTERNS = {
    "tr": {
        "auth_refusal": {
            "keywords": ["kimligimi vermek istemiyorum", "kimlik vermek istemiyorum", "kimligimi paylasmak", "vermeyecegim", "paylasma"],
            "response": "Kimlik dogrulamasi olmadan kisisel bilgilere erisemiyorum. Ancak genel sorulariniza yardimci olabilirim. Ne sormak istersiniz?",
        },
        "third_party": {
            "keywords": ["arkadasimin", "esimin", "annemin", "babamin", "kardesimin", "baskasinin", "onun basvurusu"],
            "response": "Guvenlik nedeniyle sadece kendi kimliginizle dogrulama yapabilirsiniz. Sormak istediginiz kisinin bizzat aramasi gerekiyor.",
        },
        "partial_tc": {
            "keywords": ["sonu", "ile biten", "son hanesi", "ilk hanesi", "hatirlamiyorum", "tam bilmiyorum"],
            "response": "Dogrulama icin 11 haneli TC Kimlik numarasinin tamamina ihtiyacim var. Kimlik kartinizin on yuzunde yazıyor. Lutfen tam numarayi soyler misiniz?",
        },
        "robot_question": {
            "keywords": ["robot musun", "gercek insan", "yapay zeka", "bot musun", "insan misin", "makine misin"],
            "response": "Ben Umut, Vatandas Hizmetleri sesli asistaniyim. Yapay zeka destekli bir sistemim. Size devlet hizmetleri konusunda yardimci olabilirim. Isterseniz bir insan operatore de baglayabilirim.",
        },
        "anger": {
            "keywords": ["siktir", "amina", "orospu", "salak", "aptal", "gerizekali", "lanet", "sikeyim"],
            "response": "Uzgunlugunuzu anliyorum. Size daha iyi yardimci olabilmesi icin sizi bir operatore bagliyorum.",
        },
        "previous_call": {
            "keywords": ["gecen aradigimda", "daha once aramistim", "onceki gorusmemde", "gecen sefer"],
            "response": "Maalesef onceki gorusmelerin detaylarina erisemiyorum. Size simdi nasil yardimci olabilirim? Basvuru durumu sorgulamak, randevu almak veya genel bilgi almak isterseniz yardimci olabilirim.",
        },
    },
    "en": {
        "auth_refusal": {
            "keywords": ["don't want to give my id", "refuse to provide", "won't share my id", "not giving"],
            "response": "I cannot access personal information without identity verification. However, I can help with general questions. What would you like to know?",
        },
        "third_party": {
            "keywords": ["my friend's", "my wife's", "my husband's", "someone else's", "their application", "my mother's", "my father's"],
            "response": "For security reasons, I can only verify your own identity. The person in question would need to call us directly.",
        },
        "partial_tc": {
            "keywords": ["ending in", "starts with", "last digits", "don't remember the full", "partial"],
            "response": "I need the full 11-digit TC Kimlik number for verification. You can find it on the front of your ID card. Could you please provide the complete number?",
        },
        "robot_question": {
            "keywords": ["are you a robot", "real person", "artificial intelligence", "are you a bot", "are you human", "machine"],
            "response": "I'm Umut, the Citizen Services voice assistant. I'm an AI-powered system. I can help you with government services. If you prefer, I can connect you with a human operator.",
        },
        "anger": {
            "keywords": ["fuck", "shit", "damn", "stupid", "idiot", "bullshit", "asshole"],
            "response": "I understand your frustration. Let me connect you with a human operator who can better assist you.",
        },
        "previous_call": {
            "keywords": ["last time i called", "previous call", "when i called before", "last conversation"],
            "response": "I'm sorry, I don't have access to previous call details. How can I help you now? I can check application status, book appointments, or provide general information.",
        },
    },
}


def _check_edge_case(user_query: str, language: str) -> str | None:
    """Check if user message matches a known edge case pattern.

    Returns a direct response if matched, None otherwise.
    """
    patterns = EDGE_CASE_PATTERNS.get(language, EDGE_CASE_PATTERNS["tr"])
    query_lower = user_query.lower()

    for case_name, case_data in patterns.items():
        for keyword in case_data["keywords"]:
            if keyword in query_lower:
                logger.info(f"Edge case detected: {case_name} | query='{user_query[:50]}'")
                return case_data["response"]

    return None


RAG_SYSTEM_PROMPT = """You are a government citizen services assistant named Umut.
Answer the user's question based ONLY on the provided context documents.

Rules:
- Only use information from the provided context. Do not make up information.
- If the context does not contain the answer, say so honestly and offer to connect with a human operator.
- Mention the source category briefly when answering.
- CRITICAL: Your response will be spoken aloud by a voice agent, NOT displayed as text.
  - Never use tables, bullet points, markdown formatting, or numbered lists.
  - Convert all structured data into natural conversational sentences.
  - For schedules: "Hafta ici her gun sabah sekizden aksam bese kadar hizmet veriyoruz" instead of listing each day.
  - For document lists: "Basvuru icin kimlik karti, iki adet fotograf ve harc dekontu gerekiyor" instead of bullet points.
  - For fees: "On yillik pasaport ucreti bes bin yedi yuz elli lira" instead of tables.
  - Keep it concise — a phone caller doesn't want to hear a long list read out.
  - Summarize where possible, offer to provide more details if needed.
- If the context documents do NOT contain the specific information the user is asking about, say "Bu konuda elimde kesin bir bilgi yok" — do NOT guess, infer, or add details not explicitly stated in the context.
- Do NOT add specific numbers (minutes, amounts, dates) that are not in the context. If the context says "dilim" but not "15 dakika", do NOT say "15 dakikalık dilimler".
- Do NOT suggest transferring to a human operator unless the user explicitly asks for it or the question is truly unanswerable.
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

    # Step 0: Check edge cases BEFORE RAG — these need direct responses, not retrieval
    edge_response = _check_edge_case(user_query, language)
    if edge_response:
        from langchain_core.messages import AIMessage
        return {
            "messages": [AIMessage(content=edge_response)],
            "completed_intents": mark_completed(state, state.get("current_intent", "faq")),
        }

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
