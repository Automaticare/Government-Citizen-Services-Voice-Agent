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

ElevenLabs Workflow (auth):
  Start → Collect Identity (GPT-4o) → Dispatch tool (webhook auth)
    → Success: Authenticated Service (Custom LLM / LangGraph)
    → Failure: Auth Retry (GPT-4o) → back to Collect Identity

Single FastAPI server (agent/server.py, port 8080):
├─ /v1/chat/completions — Custom LLM proxy (ElevenLabs → LangGraph → SSE)
├─ /auth/*              — Government auth endpoints (mounted from api/)
├─ /appointments/*      — Appointment endpoints (mounted from api/)
├─ /documents/*         — Document request endpoints (mounted from api/)
├─ /services            — Service catalog (mounted from api/)
└─ /health              — Health check + circuit breaker status
```

## Project Structure
```
/agent              — LangGraph agent core
  /nodes            — Graph node implementations (intent_classify, status_check, etc.)
  /prompts          — Versioned system prompts (v1.0/system_prompt_tr.md, _en.md)
  /tools            — Validators (tc_kimlik.py, app_ref.py)
  config.py         — AgentConfig dataclass (incl. custom_llm_url)
  deploy.py         — Programmatic agent deploy to ElevenLabs (conversation config, workflow preserved)
  graph.py          — LangGraph StateGraph definition
  logging_config.py — PII redaction logging
  server.py         — Custom LLM proxy + mounted gov API (/v1/chat/completions SSE, circuit breaker)
  state.py          — AgentState TypedDict
/api                — Government backend (mounted into agent/server.py)
  auth.py           — POST /auth/verify/tc-kimlik, /auth/verify/app-ref, /auth/verify/webhook
  handoff.py        — POST /handoff, POST /guest/info
  models.py         — SQLAlchemy models (Citizen, AuthAuditLog, Appointment, DocumentRequest)
  seed_data.py      — 23 citizen records + 5 appointments + 3 doc requests seeder
  services.py       — GET /applications/{ref}, POST /appointments, POST /documents/request, GET /services
  server.py         — Standalone FastAPI app (for independent testing)
/dashboard          — Streamlit analytics app (planned)
/data               — citizens.db (SQLite, gitignored)
/docs               — auth_flow.md, conversation_flow.md
/tests              — 119 tests total (94 unit + 25 live API)
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
- **Stateless message passing** — ElevenLabs sends full history each turn, no server-side checkpointer needed
- **Graceful degradation** — Level 0: full LangGraph, Level 1: direct OpenAI (circuit breaker after 3 failures, 60s cooldown), Level 2: ElevenLabs native fallback (backup_llm_config)
- **Sentence-level SSE streaming** — responses split by sentence with delays for TTS processing
- **STT-friendly auth** — last 4 digits + DOB + father initial instead of full 11-digit TC Kimlik

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
- Tests: `python -m pytest tests/ -v` (119 tests total — 94 unit + 25 live API tests)
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

# 4. Start server (single server — gov API mounted into agent server)
python -m uvicorn agent.server:app --reload --port 8080

# 5. Start ngrok tunnel (for ElevenLabs to reach our server)
ngrok http 8080

# 6. Deploy agent to ElevenLabs (conversation config only — workflow preserved)
$env:CUSTOM_LLM_URL="<ngrok-url>"; python -m agent.deploy
python -m agent.deploy --dry-run # Preview without deploying

# 7. Run tests
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
- **ISSUE-08:** Connect LangGraph to ElevenLabs Voice — transfer_to_number system tool call, buffer words, circuit breaker (Level 0/1/2 degradation), Custom LLM deploy config, backup_llm_config, conversation.py removed
- **ISSUE-09:** Tool Schemas — 5 business tools (Pydantic validation + OpenAI format registry), 3 system tools (language_detection + end_call deployed, transfer_to_number deferred to Twilio), 22 tests
- **ISSUE-10:** Knowledge Base — 40 documents (5 categories × 4 doc types × 2 languages), manifest.json
- **ISSUE-11:** Embedding Pipeline — chunker (253 chunks from 40 docs), OpenAI text-embedding-3-small, Pinecone serverless index, 5/5 validation queries passing
- **ISSUE-12:** RAG Integration — faq_answer grounded in Pinecone (no hallucination), status_check chains to RAG for required docs + appeal rights
- **ISSUE-13:** Mock Government API — Appointment and DocumentRequest DB models, 5 API endpoints, seed data (23 citizens, 5 appointments, 3 doc requests)
  - **Debt:** Application table needs 1:N separation from Citizen, missing cancel/status endpoints
- **ISSUE-14:** Tool Calling — Nodes connected to real API via httpx, tool chaining (status → RAG), 15 services tests
  - **Debt:** Missing appointment_list, appointment_cancel, document_status nodes
- **ISSUE-15:** Edge Cases — LLM-based handling (no hardcoded keywords), platform settings, TTS-friendly SSE streaming

### Auth Workflow (ISSUE-05B) — COMPLETE
- ElevenLabs Workflow: Start → Collect Identity (GPT-4o) → Dispatch tool (webhook) → Success: Authenticated Service (Custom LLM/LangGraph) / Failure: Auth Retry (GPT-4o) → back to Collect Identity
- Auth method: TC Kimlik last 4 digits + DOB + father's name initial (STT-friendly)
- Webhook: POST /auth/verify/webhook — returns 200 on success, 401 on failure (generic error message, no field-specific info leak)
- Dynamic variables: first_name, application_ref, application_status injected into system prompt by ElevenLabs, parsed by Custom LLM proxy
- Post-auth detection: server.py identifies auth artifacts in message history, extracts original user request
- Workflow configured via dashboard (tool node requires dashboard webhook config), deploy script preserves workflow

### What Works Now (e2e tested via dashboard):
- ✅ FAQ/RAG — "Çalışma saatleri?", "Pasaport belgeleri?", "Ehliyet ücreti?" (TTS-friendly, no digits)
- ✅ Auth flow — collect identity → dispatch tool → success/failure routing
- ✅ Auth + status check — "Başvurumun durumunu öğrenmek istiyorum" → auth → "Ahmet, başvurunuz inceleme aşamasında"
- ✅ Auth failure — wrong credentials → Auth Retry → "tekrar denemek ister misiniz?"
- ✅ Edge cases — auth refusal, third-party block, robot question, anger → escalate
- ✅ Complaint recording
- ✅ Operator transfer (demo mode)
- ⚠️ Auth + appointment/document — not yet e2e tested but code ready
- ⚠️ Tool chaining (status → RAG for docs) — works in terminal, not yet e2e tested with auth

### Technical Debt
- Application table 1:1 with Citizen (should be 1:N) — ISSUE-13 debt
- Missing appointment_list, appointment_cancel, document_status nodes — ISSUE-14 debt
- Buffer words after auth ("kontrol ediyorum") — causes workflow edge issues, deferred
- Server.py has debug logging (last_system_prompt.txt) — remove before production

### Remaining Issues (not started)
- **ISSUE-15B:** Twilio Phone Integration
- **ISSUE-16-18:** Conversation Management
- **ISSUE-19-22:** Analytics Dashboard (Streamlit)
- **ISSUE-23-25:** Testing & Quality
- **ISSUE-26-28:** Documentation & Demo
