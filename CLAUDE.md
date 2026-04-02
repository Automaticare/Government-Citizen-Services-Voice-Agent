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

## Development Guidelines
- Use `.env` for secrets, never commit API keys
- All conversation logs must redact personal data (TC Kimlik, DOB)
- System prompts live in versioned files under `/agent/prompts/`
- Tests runnable via `python -m pytest tests/`
- Eval suite via `python -m tests.eval`

## Current Status
- ISSUE-01: Project Setup & ElevenLabs Agent Initialization — IN PROGRESS
