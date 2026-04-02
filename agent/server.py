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
import uuid

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langgraph.checkpoint.memory import MemorySaver

from agent.graph import build_graph
from agent.logging_config import get_logger
from agent.prompts.loader import get_latest_version

logger = get_logger(__name__)

# Build graph with checkpointer for state persistence across turns
checkpointer = MemorySaver()
_compiled_graph = build_graph(checkpointer=checkpointer)


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


# --- Graph runner ---

def _extract_conversation_id(request: ChatCompletionRequest) -> str:
    """Extract conversation ID from ElevenLabs extra body or generate one."""
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


# --- Endpoint ---

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint for ElevenLabs Custom LLM."""
    conversation_id = _extract_conversation_id(request)
    auth_status, citizen_profile = _extract_auth_state(request)

    logger.info(f"Custom LLM request | conv={conversation_id} | messages={len(request.messages)}")

    # Convert request messages to LangGraph format
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

    lc_messages = []
    for msg in request.messages:
        content = msg.content or ""
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif msg.role == "assistant":
            lc_messages.append(AIMessage(content=content))
        elif msg.role == "system":
            lc_messages.append(SystemMessage(content=content))

    # Only pass the latest user message to avoid re-processing history
    # (checkpointer handles state persistence)
    latest_messages = [lc_messages[-1]] if lc_messages else []

    graph = _compiled_graph
    config = {"configurable": {"thread_id": conversation_id}}

    async def stream():
        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        sent_role = False

        try:
            # Build input — only pass messages + auth context from ElevenLabs.
            # Other state fields (completed_intents, current_intent) are
            # preserved by the checkpointer across turns.
            graph_input = {"messages": latest_messages}

            # Auth context from ElevenLabs extra_body — only set if provided,
            # otherwise checkpointer preserves previous values.
            if auth_status != "unauthenticated":
                graph_input["auth_status"] = auth_status
            if citizen_profile:
                graph_input["citizen_profile"] = citizen_profile

            # Stream with message-level granularity
            async for message_chunk, metadata in graph.astream(
                graph_input,
                config=config,
                stream_mode="messages",
            ):
                # Filter: only forward model text chunks (skip tool calls)
                node = metadata.get("langgraph_node", "")
                content = getattr(message_chunk, "content", None)

                if not content:
                    continue

                # Skip non-terminal nodes (intent_classify, service_router)
                # Forward only service node responses
                if node in ("intent_classify", "service_router"):
                    continue

                if not sent_role:
                    yield sse_chunk(response_id, {"role": "assistant"})
                    sent_role = True

                yield sse_chunk(response_id, {"content": content})

        except Exception as e:
            logger.error(f"Graph execution error: {e}")
            if not sent_role:
                yield sse_chunk(response_id, {"role": "assistant"})
            yield sse_chunk(response_id, {"content": "Bir hata olustu. Lutfen tekrar deneyin."})

        yield sse_chunk(response_id, {}, finish_reason="stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/health")
def health():
    return {"status": "ok", "agent": "langgraph-citizen-services"}
