"""
Status check node.

Queries the application status and chains results deterministically:
- If "additional_docs_needed" → RAG query for required documents (Pinecone)
- If "rejected" → RAG query for appeal rights + guidance
- Otherwise → return status directly

This is LangGraph's core differentiator: deterministic tool chaining.
ElevenLabs native tools can't guarantee "status API returned X,
therefore automatically query knowledge base for Y."
"""

from langchain_core.messages import AIMessage

from agent.state import AgentState
from agent.logging_config import get_logger
from agent.nodes.utils import mark_completed
from rag.retriever import search, format_context

logger = get_logger(__name__)


def _rag_lookup(query: str, language: str, category: str | None = None) -> str:
    """Query RAG for supplementary information. Returns formatted context or empty string."""
    results = search(query=query, language=language, category=category, top_k=2)
    if results and results[0].score > 0.3:
        return format_context(results)
    return ""


def status_check(state: AgentState) -> dict:
    """Check application status with deterministic tool chaining."""
    profile = state.get("citizen_profile")
    language = state.get("language", "tr")

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
        # Chain: status → RAG query for required documents
        rag_query = "required documents for application" if language == "en" else "basvuru icin gerekli belgeler"
        docs_context = _rag_lookup(rag_query, language)
        logger.info(f"Tool chain: status=additional_docs_needed -> RAG docs lookup (found={bool(docs_context)})")

        if language == "en":
            msg = f"{first_name}, your application {app_ref} requires additional documents."
            if docs_context:
                msg += f"\n\nBased on our records, you may need:\n{docs_context}"
            msg += "\nPlease submit these at your nearest citizen services office."
        else:
            msg = f"{first_name}, {app_ref} numarali basvurunuz ek belge gerektiriyor."
            if docs_context:
                msg += f"\n\nKayitlarimiza gore gerekli olabilecek belgeler:\n{docs_context}"
            msg += "\nBu belgeleri en yakin vatandas hizmetleri ofisine teslim edebilirsiniz."

    elif status == "rejected":
        # Chain: status → RAG query for appeal rights
        rag_query = "appeal rights rejected application" if language == "en" else "itiraz hakki reddedilen basvuru"
        appeal_context = _rag_lookup(rag_query, language, category="general")
        logger.info(f"Tool chain: status=rejected -> RAG appeal lookup (found={bool(appeal_context)})")

        if language == "en":
            msg = f"{first_name}, your application {app_ref} has been rejected."
            if appeal_context:
                msg += f"\n\nAppeal information:\n{appeal_context}"
            else:
                msg += ("\nYou may file an appeal within 30 days of the rejection date. "
                        "For legal guidance, we recommend consulting a lawyer.")
        else:
            msg = f"{first_name}, {app_ref} numarali basvurunuz reddedilmistir."
            if appeal_context:
                msg += f"\n\nItiraz bilgileri:\n{appeal_context}"
            else:
                msg += ("\nRed tarihinden itibaren 30 gun icinde itiraz basvurusu yapabilirsiniz. "
                        "Hukuki danismanlik icin bir avukata basvurmanizi oneririz.")

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
