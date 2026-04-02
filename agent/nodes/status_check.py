"""
Status check node.

Queries the application status API and chains results:
- If "additional_docs_needed" → auto describe required documents
- If "rejected" + recent → offer appeal guidance
- Otherwise → return status directly

This is LangGraph's core differentiator: deterministic tool chaining
that ElevenLabs native tools can't guarantee.
"""

import httpx
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from agent.state import AgentState
from agent.logging_config import get_logger
from agent.nodes.utils import mark_completed

logger = get_logger(__name__)

API_BASE = "http://localhost:8001"
_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

# Required documents per service type (mock — will come from RAG in ISSUE-10)
REQUIRED_DOCS = {
    "passport": "nufus cuzdani fotokopisi, 2 adet vesikalik fotograf, eski pasaport",
    "id_card": "nufus cuzdani fotokopisi, ikametgah belgesi, 1 adet vesikalik fotograf",
    "residence": "kira kontrati veya tapu fotokopisi, nufus cuzdani fotokopisi",
    "default": "nufus cuzdani fotokopisi, ikametgah belgesi, 2 adet vesikalik fotograf",
}


def status_check(state: AgentState) -> dict:
    """Check application status with deterministic tool chaining."""
    profile = state.get("citizen_profile")
    language = state.get("language", "tr")

    # If no profile (not authenticated), inform the user
    if not profile:
        msg = ("I need to verify your identity before checking your application status."
               if language == "en" else
               "Basvuru durumunuzu kontrol etmek icin kimlik dogrulamasi gerekiyor.")
        return {
            "messages": [AIMessage(content=msg)],
            "completed_intents": mark_completed(state, "status_check"),
        }

    app_ref = profile.get("application_ref", "")
    status = profile.get("application_status", "unknown")
    first_name = profile.get("first_name", "")

    # --- Deterministic tool chaining based on status ---

    if status == "additional_docs_needed":
        # Chain: status result → auto lookup required documents
        docs = REQUIRED_DOCS.get("default")
        logger.info(f"Tool chain: status=additional_docs_needed -> auto docs lookup")

        if language == "en":
            msg = (f"{first_name}, your application {app_ref} requires additional documents. "
                   f"Required documents: {docs}. "
                   f"Please submit these at your nearest citizen services office.")
        else:
            msg = (f"{first_name}, {app_ref} numarali basvurunuz ek belge gerektiriyor. "
                   f"Gerekli belgeler: {docs}. "
                   f"Bu belgeleri en yakin vatandas hizmetleri ofisine teslim edebilirsiniz.")

    elif status == "rejected":
        # Chain: status result → check appeal eligibility
        logger.info(f"Tool chain: status=rejected -> appeal guidance")

        if language == "en":
            msg = (f"{first_name}, your application {app_ref} has been rejected. "
                   f"You may file an appeal within 30 days of the rejection date. "
                   f"For legal guidance, we recommend consulting a lawyer.")
        else:
            msg = (f"{first_name}, {app_ref} numarali basvurunuz reddedilmistir. "
                   f"Red tarihinden itibaren 30 gun icinde itiraz basvurusu yapabilirsiniz. "
                   f"Hukuki danismanlik icin bir avukata basvurmanizi oneririz.")

    elif status == "approved":
        if language == "en":
            msg = (f"{first_name}, your application {app_ref} has been approved. "
                   f"You can collect your documents at the nearest citizen services office.")
        else:
            msg = (f"{first_name}, {app_ref} numarali basvurunuz onaylanmistir. "
                   f"Belgelerinizi en yakin vatandas hizmetleri ofisinden teslim alabilirsiniz.")

    elif status == "in_review":
        if language == "en":
            msg = (f"{first_name}, your application {app_ref} is currently under review. "
                   f"Estimated completion time is 5-10 business days.")
        else:
            msg = (f"{first_name}, {app_ref} numarali basvurunuz inceleme asamasindadir. "
                   f"Tahmini tamamlanma suresi 5-10 is gunudur.")

    else:  # pending or unknown
        if language == "en":
            msg = (f"{first_name}, your application {app_ref} is currently in '{status}' status. "
                   f"Is there anything else I can help you with?")
        else:
            msg = (f"{first_name}, {app_ref} numarali basvurunuz su anda '{status}' durumundadir. "
                   f"Baska yardimci olabilecegim bir konu var mi?")

    return {
        "messages": [AIMessage(content=msg)],
        "completed_intents": mark_completed(state, "status_check"),
    }


