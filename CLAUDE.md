# CLAUDE.md

## Project Overview
Government Citizen Services Voice Agent — an AI-powered multilingual voice agent (Turkish + English) for government citizen services. Built on ElevenLabs Conversational AI with a custom LangGraph backend, RAG pipeline (Pinecone), and Streamlit analytics dashboard.

**Context:** This is an FDE (Forward Deployed Engineer) demo project for ElevenLabs. The architecture should demonstrate both platform mastery (ElevenLabs native features) and engineering depth (Custom LLM + LangGraph). Reference: Oscar's guidance says LangGraph + Custom LLM is the expected approach.

## Tech Stack
- **Voice Layer:** ElevenLabs Conversational AI (STT + TTS)
- **Agent Backend:** LangGraph (multi-step workflow orchestration)
- **API Bridge:** FastAPI (Custom LLM endpoint for ElevenLabs)
- **RAG:** Pinecone (vector DB) + OpenAI embeddings
- **Database:** SQLite (demo) / PostgreSQL (production) via SQLAlchemy ORM
- **Dashboard:** Streamlit
- **Language:** Python 3.11+

## Architecture
```
ElevenLabs (platform-native):          LangGraph (custom intelligence):
├─ Voice (STT/TTS)                     ├─ Intent classification (GPT-4o-mini)
├─ Language detection (system tool)     ├─ Multi-step service routing
├─ Auth gating (workflow dispatch)      ├─ Tool orchestration (API calls)
└─ Degradation fallback                ├─ Deterministic tool chaining
                                       ├─ Conversation state (MemorySaver)
                                       └─ Prompt versioning

Two FastAPI servers:
├─ api/server.py    (port 8001) — Government backend: auth, handoff, guest FAQ, citizen DB
└─ agent/server.py  (port 8000) — Custom LLM proxy: ElevenLabs → LangGraph → SSE stream
```

## Project Structure
```
/agent              — LangGraph agent core
  /nodes            — Graph node implementations (intent_classify, status_check, etc.)
  /prompts          — Versioned system prompts (v1.0/system_prompt_tr.md, _en.md)
  /tools            — Validators (tc_kimlik.py, app_ref.py)
  config.py         — AgentConfig dataclass
  conversation.py   — Direct ElevenLabs conversation (TO BE REMOVED in ISSUE-08)
  deploy.py         — Programmatic agent deploy to ElevenLabs
  graph.py          — LangGraph StateGraph definition
  logging_config.py — PII redaction logging
  server.py         — Custom LLM proxy (/v1/chat/completions SSE)
  state.py          — AgentState TypedDict
/api                — Government backend
  auth.py           — POST /auth/verify/tc-kimlik, /auth/verify/app-ref
  handoff.py        — POST /handoff, POST /guest/info
  models.py         — SQLAlchemy models (Citizen, AuthAuditLog)
  seed_data.py      — 23 citizen records seeder
  server.py         — FastAPI app (port 8001)
/dashboard          — Streamlit analytics app (planned)
/data               — citizens.db (SQLite, gitignored)
/docs               — auth_flow.md, conversation_flow.md
/tests              — 77 tests total
  conftest.py       — Shared test DB setup with per-test audit log cleanup
  /eval             — Automated conversation evaluation (planned)
```

## Key Design Decisions
- **ElevenLabs Workflows for auth gating** — deterministic dispatch tool + subagent isolation (not LLM-based)
- **LangGraph for intelligence** — intent routing, tool chaining, state management (what ElevenLabs native can't guarantee)
- **LangGraph's core differentiator:** deterministic tool chaining (status "additional_docs_needed" → auto RAG query, "rejected" → appeal guidance)
- **Single multilingual agent** with language_presets — one endpoint, auto language detection
- **KVKK compliance** — PII redaction in all logs, TC Kimlik stored as SHA-256 hash, audit trail with no raw PII
- **Prompt versioning** tracked per conversation for data-driven optimization
- **MemorySaver checkpointer** keyed by conversation_id for state persistence across turns

## README Policy
- README contains the FULL target project structure — not just what exists today
- Never strip future/planned items from README — an evaluator should see the full vision upfront

## Development Guidelines
- Always use `from agent.logging_config import get_logger` — never use `print()` or raw `logging`
- PII redaction is automatic — TC Kimlik (11 digits) and DOB patterns are masked before log output
- Use `.env` for secrets, never commit API keys
- System prompts live in versioned files under `/agent/prompts/`
- Shared node utilities in `agent/nodes/utils.py` (e.g., mark_completed)
- `load_dotenv()` is called once in `agent/graph.py` — not in individual nodes
- Tests: `python -m pytest tests/ -v` (77 tests, all passing)
- Test DB: in-memory SQLite via conftest.py, audit log cleaned per test

## User Preferences (for Claude)
- User communicates in Turkish
- User does manual git commits — provide commit messages with Co-Authored-By line, never auto-commit
- Update CLAUDE.md after every development step
- Update issues.md task checkboxes as work completes
- Think like a senior FDE — business value over over-engineering
- Ask questions before making assumptions
- When editing README, keep full target structure (don't strip planned items)

## How to Run
```bash
# 1. Clone and setup
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Fill in: ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID, OPENAI_API_KEY

# 3. Seed the citizen database
python -m api.seed_data

# 4. Start servers (two separate terminals)
uvicorn api.server:app --reload --port 8001    # Government API
uvicorn agent.server:app --reload --port 8000  # Custom LLM proxy

# 5. Deploy agent to ElevenLabs
python -m agent.deploy           # Deploy multilingual agent
python -m agent.deploy --dry-run # Preview without deploying

# 6. Run tests
make test              # Unit tests (no API keys needed for most)
make test-live         # Live API + simulation tests
```

## Current Status

### Completed Issues
- **ISSUE-01:** Project Setup — repo structure, .env, requirements, logging with PII redaction
- **ISSUE-02:** Agent Persona — system prompts v1.0 (TR+EN), 7 intents, guardrails, deploy script, 11 simulation tests
- **ISSUE-03:** Multilingual — single agent with language_presets, language detection system tool, 5 language tests
- **ISSUE-04:** Auth Flow Design — workflow-based deterministic auth (ElevenLabs blog pattern), KVKK compliance, TC Kimlik checksum
- **ISSUE-05:** Auth Implementation — SQLite+SQLAlchemy, FastAPI auth endpoints, 20 tests, progressive failure guidance
- **ISSUE-06:** Failure Handling — handoff endpoint, guest mode FAQ, 10 tests
- **ISSUE-07:** LangGraph Workflow — 8-node graph, LLM intent classification, deterministic tool chaining, Custom LLM proxy with SSE streaming, MemorySaver checkpointer, 24 tests

### Next: ISSUE-08 — Connect LangGraph to ElevenLabs Voice
Remaining tasks:
- [ ] System tool calls (end_call, transfer_to_number) in OpenAI function call format from escalate node
- [ ] Buffer words for slow processing ("Bir saniye bakıyorum... ")
- [ ] Remove agent/conversation.py (replaced by Custom LLM proxy)
- [ ] Update deploy script to configure Custom LLM endpoint on ElevenLabs
- [ ] Set up public URL (ngrok) for ElevenLabs to reach our server
- [ ] End-to-end voice test
- [ ] Graceful degradation (at least Level 0 + Level 2)
- [ ] Latency measurement

### Remaining Issues (not started)
- ISSUE-09: Define Agent Tools & Function Schemas
- ISSUE-10-12: RAG Pipeline (Pinecone)
- ISSUE-13-15: Tool Calling & Integrations (Mock Gov API)
- ISSUE-16-18: Conversation Management
- ISSUE-19-22: Analytics Dashboard (Streamlit)
- ISSUE-23-25: Testing & Quality
- ISSUE-26-28: Documentation & Demo
