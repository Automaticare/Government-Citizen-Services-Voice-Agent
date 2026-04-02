"""
Custom LLM proxy server for ElevenLabs.

Translates between ElevenLabs' OpenAI-compatible request format
and LangGraph's streaming output. Follows the FDE team's blog
pattern: receive messages → run agent → stream filtered SSE chunks.

Run:
    uvicorn agent.server:app --reload --port 8000

Reference:
    https://elevenlabs.io/blog/practical-guide-open-source-agent-frameworks-and-elevenagents
"""

import json
import time
import uuid

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel

from agent.graph import build_graph
from agent.logging_config import get_logger
from agent.prompts.loader import load_system_prompt, get_latest_version

logger = get_logger(__name__)

# Build graph without checkpointer — ElevenLabs is stateless and sends
# full message history with every request, so no server-side persistence needed.
_compiled_graph = build_graph()


# --- Circuit breaker (graceful degradation) ---
#
# Tracks consecutive LangGraph failures. When threshold is exceeded,
# proxy switches to Level 1 degradation: direct OpenAI call with
# system prompt, bypassing the graph.
#
# Levels:
#   0 — Healthy: full LangGraph agent
#   1 — Degraded: direct OpenAI LLM call (bypass graph)
#   2 — Down: ElevenLabs falls back to its default agent
#       (configured via backup_llm_config in deploy script)
#

_CB_THRESHOLD = 3          # consecutive failures before opening circuit
_CB_COOLDOWN_SECONDS = 60  # seconds before retrying LangGraph
_cb_failures = 0
_cb_opened_at: float | None = None


def _cb_record_success() -> None:
    """Reset circuit breaker on successful graph execution."""
    global _cb_failures, _cb_opened_at
    if _cb_failures > 0:
        logger.info(f"Circuit breaker reset after {_cb_failures} failures")
    _cb_failures = 0
    _cb_opened_at = None


def _cb_record_failure() -> None:
    """Record a graph failure. Opens circuit after threshold."""
    global _cb_failures, _cb_opened_at
    _cb_failures += 1
    if _cb_failures >= _CB_THRESHOLD and _cb_opened_at is None:
        _cb_opened_at = time.time()
        logger.warning(f"Circuit breaker OPEN — {_cb_failures} consecutive failures, switching to Level 1")


def _cb_is_open() -> bool:
    """Check if circuit breaker is open (Level 1 degradation active).

    Auto-closes after cooldown to allow retrying LangGraph.
    """
    global _cb_failures, _cb_opened_at
    if _cb_failures < _CB_THRESHOLD:
        return False
    # Allow retry after cooldown
    if _cb_opened_at and (time.time() - _cb_opened_at) > _CB_COOLDOWN_SECONDS:
        logger.info("Circuit breaker cooldown expired — retrying LangGraph")
        _cb_failures = 0
        _cb_opened_at = None
        return False
    return True


def _cb_status() -> dict:
    """Return circuit breaker state for health endpoint."""
    if _cb_is_open():
        return {"level": 1, "label": "degraded", "failures": _cb_failures}
    return {"level": 0, "label": "healthy", "failures": _cb_failures}


app = FastAPI(
    title="Citizen Services Custom LLM",
    version="0.1.0",
    description="LangGraph agent exposed as OpenAI-compatible Custom LLM for ElevenLabs.",
)


# --- Request model (OpenAI Chat Completions format) ---

class Message(BaseModel):
    role: str
    content: str | None = None

class ChatCompletionRequest(BaseModel):
    messages: list[Message]
    model: str = "langgraph-citizen-agent"
    temperature: float | None = 0.7
    max_tokens: int | None = None
    stream: bool | None = True
    tools: list[dict] | None = None  # System tools sent by ElevenLabs
    elevenlabs_extra_body: dict | None = None


# --- SSE helper (from FDE blog) ---

def sse_chunk(response_id: str, delta: dict, finish_reason: str | None = None) -> str:
    """Format a single SSE chunk in OpenAI chat completion format."""
    payload = {
        "id": response_id,
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(payload)}\n\n"


# --- Request helpers ---

def _extract_conversation_id(request: ChatCompletionRequest) -> str:
    """Extract conversation ID from ElevenLabs extra body or generate one.

    Used for logging only — ElevenLabs is stateless and sends full
    message history with every request, so no server-side state needed.
    """
    if request.elevenlabs_extra_body:
        conv_id = request.elevenlabs_extra_body.get("conversation_id")
        if conv_id:
            return conv_id
    return f"local-{uuid.uuid4().hex[:12]}"


def _extract_auth_state(request: ChatCompletionRequest) -> tuple[str, dict | None]:
    """Extract auth status and citizen profile from extra body."""
    if request.elevenlabs_extra_body:
        auth_status = request.elevenlabs_extra_body.get("auth_status", "unauthenticated")
        profile = request.elevenlabs_extra_body.get("citizen_profile")
        return auth_status, profile
    return "unauthenticated", None


def _detect_language(text: str) -> str:
    """Detect language from message text using simple heuristics.

    Checks for Turkish-specific characters and common words.
    Returns 'tr' or 'en'.
    """
    turkish_chars = set("çğıöşüÇĞİÖŞÜ")
    if any(c in turkish_chars for c in text):
        return "tr"

    turkish_words = {"merhaba", "nasıl", "yardım", "teşekkür", "lütfen",
                     "evet", "hayır", "bilgi", "başvuru", "randevu",
                     "nedir", "istiyorum", "olabilir", "benim", "için"}
    words = set(text.lower().split())
    if words & turkish_words:
        return "tr"

    return "en"


def _extract_language(request: ChatCompletionRequest) -> str:
    """Detect language from the latest user message content.

    Falls back to extra_body language or 'tr' default.
    """
    # Detect from latest user message
    for msg in reversed(request.messages):
        if msg.role == "user" and msg.content:
            return _detect_language(msg.content)

    # Fallback to extra_body or default
    if request.elevenlabs_extra_body:
        return request.elevenlabs_extra_body.get("language", "tr")
    return "tr"


def _detect_previous_language(request: ChatCompletionRequest) -> str | None:
    """Detect language from the second-to-last user message.

    Returns None if there's only one user message (first turn).
    """
    user_messages = [m for m in request.messages if m.role == "user" and m.content]
    if len(user_messages) < 2:
        return None
    return _detect_language(user_messages[-2].content)


def _buffer_word(language: str) -> str:
    """Return a buffer word for slow processing in the detected language.

    Trailing space is intentional — ElevenLabs docs require it to prevent
    audio artifacts when the next chunk arrives.
    """
    if language == "en":
        return "One moment please... "
    return "Bir saniye bakiyorum... "


# --- Level 1 fallback (direct OpenAI call, bypass LangGraph) ---

async def _level1_fallback(messages: list, language: str):
    """Level 1 degradation: direct OpenAI call with system prompt.

    Bypasses LangGraph graph — no intent routing, no tool chaining,
    no deterministic flows. Just a simple LLM conversation with the
    system prompt for basic citizen guidance.
    """
    from openai import AsyncOpenAI

    system_prompt = load_system_prompt(language=language, version=get_latest_version())
    openai_messages = [{"role": "system", "content": system_prompt}]

    for m in messages:
        if isinstance(m, HumanMessage):
            openai_messages.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            openai_messages.append({"role": "assistant", "content": m.content or ""})

    try:
        client = AsyncOpenAI()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=openai_messages,
            stream=True,
            temperature=0.7,
            max_tokens=512,
        )
        async for chunk in response:
            delta_content = chunk.choices[0].delta.content
            if delta_content:
                yield delta_content

    except Exception as e:
        logger.error(f"Level 1 fallback error: {e}")
        if language == "en":
            yield "We are experiencing technical difficulties. Please try again later."
        else:
            yield "Teknik bir sorun yasiyoruz. Lutfen daha sonra tekrar deneyin."


# --- Endpoint ---

@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint for ElevenLabs Custom LLM."""
    conversation_id = _extract_conversation_id(request)
    auth_status, citizen_profile = _extract_auth_state(request)
    language = _extract_language(request)

    # Detect language from latest user message and check for language switch
    prev_language = _detect_previous_language(request)
    language_switched = prev_language is not None and language != prev_language

    logger.info(f"Custom LLM request | conv={conversation_id} | messages={len(request.messages)} | lang={language}")
    if language_switched:
        logger.info(f"Language switch detected: {prev_language} → {language}")

    # Convert request messages to LangGraph format
    lc_messages = []
    for msg in request.messages:
        content = msg.content or ""
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif msg.role == "assistant":
            lc_messages.append(AIMessage(content=content))
        elif msg.role == "system":
            lc_messages.append(SystemMessage(content=content))

    # ElevenLabs sends full message history with every request (stateless).
    # Pass all messages to the graph — no checkpointer needed.
    graph = _compiled_graph

    async def stream():
        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        has_tool_calls = False

        # Always send role + buffer word before processing starts.
        # LLM calls take 1-3s — buffer word keeps the conversation
        # natural while the response is being generated.
        yield sse_chunk(response_id, {"role": "assistant"})
        yield sse_chunk(response_id, {"content": _buffer_word(language)})

        if _cb_is_open():
            # Level 1 degradation: bypass LangGraph, direct OpenAI call
            logger.warning(f"Circuit breaker open — using Level 1 fallback | conv={conversation_id}")
            async for chunk in _level1_fallback(lc_messages, language):
                yield sse_chunk(response_id, {"content": chunk})
        else:
            try:
                graph_input = {"messages": lc_messages, "language": language}

                if auth_status != "unauthenticated":
                    graph_input["auth_status"] = auth_status
                if citizen_profile:
                    graph_input["citizen_profile"] = citizen_profile

                async for message_chunk, metadata in graph.astream(
                    graph_input,
                    stream_mode="messages",
                ):
                    node = metadata.get("langgraph_node", "")
                    content = getattr(message_chunk, "content", None)
                    tool_calls = getattr(message_chunk, "additional_kwargs", {}).get("tool_calls")

                    # Skip routing/classification nodes
                    if node in ("intent_classify", "service_router"):
                        continue

                    # Forward tool_calls (e.g. transfer_to_number)
                    if tool_calls:
                        has_tool_calls = True
                        tool_calls_delta = [
                            {
                                "index": i,
                                "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                                "type": "function",
                                "function": {
                                    "name": tc["function"]["name"],
                                    "arguments": tc["function"]["arguments"],
                                },
                            }
                            for i, tc in enumerate(tool_calls)
                        ]
                        yield sse_chunk(response_id, {"tool_calls": tool_calls_delta})

                    if content:
                        yield sse_chunk(response_id, {"content": content})

                _cb_record_success()

            except Exception as e:
                logger.error(f"Graph execution error: {e}")
                _cb_record_failure()
                yield sse_chunk(response_id, {"content": "Bir hata olustu. Lutfen tekrar deneyin."})

        # Emit language_detection tool call if user switched language
        if language_switched:
            has_tool_calls = True
            lang_tool_call = {
                "index": 0,
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": {
                    "name": "language_detection",
                    "arguments": json.dumps({
                        "reason": f"User switched from {prev_language} to {language}",
                        "language": language,
                    }),
                },
            }
            yield sse_chunk(response_id, {"tool_calls": [lang_tool_call]})

        finish_reason = "tool_calls" if has_tool_calls else "stop"
        yield sse_chunk(response_id, {}, finish_reason=finish_reason)
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/health")
def health():
    cb = _cb_status()
    return {
        "status": cb["label"],
        "agent": "langgraph-citizen-services",
        "degradation_level": cb["level"],
        "consecutive_failures": cb["failures"],
    }
