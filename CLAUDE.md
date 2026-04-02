# CLAUDE.md

## Project Overview
Government Citizen Services Voice Agent — an AI-powered multilingual voice agent (Turkish + English) for government citizen services. Built on ElevenLabs Conversational AI with a custom LangGraph backend, RAG pipeline (Pinecone), and Streamlit analytics dashboard.

## Tech Stack
- **Voice Layer:** ElevenLabs Conversational AI (STT + TTS)
- **Agent Backend:** LangGraph (multi-step workflow orchestration)
- **API Bridge:** FastAPI (Custom LLM endpoint for ElevenLabs)
- **RAG:** Pinecone (vector DB) + OpenAI embeddings
- **Dashboard:** Streamlit
- **Language:** Python 3.11+

## Project Structure
```
/agent              — LangGraph agent core
  /prompts          — Versioned system prompts
  /tools            — Agent tool definitions (status check, appointment, etc.)
/api                — FastAPI server (Custom LLM bridge for ElevenLabs)
/dashboard          — Streamlit analytics app
/docs               — Architecture docs, flow diagrams
/tests              — Unit and integration tests
  /eval             — Automated conversation evaluation framework
```

## Key Design Decisions
- KVKK (Turkish GDPR) compliance required — TC Kimlik must be masked in all logs
- Layered graceful degradation (4 levels) for high availability
- Prompt versioning tracked per conversation for data-driven optimization
- Cost per call tracked and displayed in dashboard (AI vs human agent ROI)

## README Policy
- README contains the FULL target project structure — not just what exists today
- As new files are created in each issue, they should already be reflected in README
- Never strip future/planned items from README — an evaluator should see the full vision upfront

## Development Guidelines
- Always use `from agent.logging_config import get_logger` — never use `print()` or raw `logging`
- PII redaction is automatic — TC Kimlik (11 digits) and DOB patterns are masked before log output
- Use `.env` for secrets, never commit API keys
- All conversation logs must redact personal data (TC Kimlik, DOB)
- System prompts live in versioned files under `/agent/prompts/`
- Tests runnable via `python -m pytest tests/`
- Eval suite via `python -m tests.eval`

## How to Run
```bash
# 1. Clone and setup
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Fill in your API keys in .env

# 3. Run a test conversation (requires microphone + speaker)
python -m agent.conversation
```

## Current Status
- ISSUE-01: Project Setup & ElevenLabs Agent Initialization — COMPLETE
  - [x] CLAUDE.md, .gitignore, .env.example
  - [x] Project folder structure + requirements.txt
  - [x] ElevenLabs agent config + conversation manager
  - [x] Agent connection tests (unit + live)
  - [x] README updated with setup instructions and full target structure
  - [x] Structured logging with PII redaction filter
  - [x] Live agent connection test — PASSED
- ISSUE-02: Agent Persona & Base Conversation Flow — IN PROGRESS
  - [x] System prompts v1.0 (TR + EN) with 7 intents, guardrails, out-of-scope handling
  - [x] Prompt loader with version management
