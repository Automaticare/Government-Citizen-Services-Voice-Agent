# Government Citizen Services Voice Agent

An AI-powered multilingual voice agent that enables citizens to access government services through natural phone conversations. Built on ElevenLabs Conversational AI with a custom LangGraph-based agent backend, RAG-powered knowledge retrieval, and real-time analytics.

## The Problem

Government call centers worldwide face the same challenges: long wait times, limited operating hours, language barriers, and high operational costs. Citizens often need simple information — application status, appointment availability, required documents — but end up waiting 20+ minutes to speak with a human agent who handles the same repetitive queries hundreds of times a day.

## The Solution

This project builds an always-on voice agent that handles citizen inquiries autonomously through natural conversation. Citizens call in, authenticate securely, and get immediate answers — whether they're checking an application status, booking an appointment, or asking about required documents. The agent speaks Turkish and English, authenticates callers securely, retrieves answers from an official knowledge base, takes real actions (booking, document requests), and escalates to humans when needed.

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│              │     │                  │     │    LangGraph Agent       │
│   Citizen    │────▶│   ElevenLabs     │────▶│                         │
│   (Phone)    │◀────│   Voice Layer    │◀────│  ┌──────────────────┐   │
│              │     │                  │     │  │ Intent Classify   │   │
└──────────────┘     │  - STT (Speech   │     │  │ Service Router    │   │
                     │    to Text)      │     │  │ Status Check      │   │
                     │  - TTS (Text     │     │  │ Appointment Book  │   │
                     │    to Speech)    │     │  │ Document Request  │   │
                     │  - Voice Models  │     │  │ FAQ Answer        │   │
                     │    (TR + EN)     │     │  │ Complaint         │   │
                     │  - Language      │     │  │ Escalate          │   │
                     │    Detection     │     │  └──────────────────┘   │
                     └──────────────────┘     └────────┬───┬───┬────────┘
                              ▲                        │   │   │
                     Custom LLM Endpoint               │   │   │
                     (FastAPI + SSE Streaming)          │   │   │
                                                       │   │   │
                              ┌─────────────────────────┘   │   └────────────────────┐
                              │                             │                        │
                              ▼                             ▼                        ▼
                     ┌────────────────┐          ┌──────────────────┐      ┌──────────────────┐
                     │  Gov Backend   │          │    Pinecone      │      │   Streamlit      │
                     │  (FastAPI)     │          │    Vector Store   │      │   Dashboard      │
                     │                │          │   (planned)      │      │   (planned)      │
                     │ - /auth/verify │          │                  │      │                  │
                     │ - /handoff     │          │  - Gov FAQs      │      │ - Call Volume    │
                     │ - /guest/info  │          │  - Regulations   │      │ - Auth Metrics   │
                     │ - Citizen DB   │          │  - Procedures    │      │ - Intent Dist.   │
                     └────────────────┘          └──────────────────┘      └──────────────────┘
```

## Core Components

### 1. ElevenLabs Voice Layer
The voice interface that citizens interact with. Handles speech-to-text, text-to-speech, and voice model selection. Supports Turkish and English with automatic language detection and dynamic voice switching. Connected to our custom LLM backend via ElevenLabs' Custom LLM endpoint.

Key platform-native features used:
- **Language detection** — system tool that auto-detects caller language and switches voice model
- **Language presets** — single agent with TR primary + EN preset, one endpoint for both languages
- **Backup LLM** — if our Custom LLM server is unreachable, ElevenLabs falls back to its native LLM (Level 2 graceful degradation)

### 2. LangGraph Agent (Custom LLM)
The brain of the system. A stateful, multi-step agent built with LangGraph that manages the entire conversation flow. Unlike a simple prompt-response chatbot, this agent maintains conversation state, makes autonomous decisions about which tools to call, and handles complex multi-intent conversations where a citizen might check their application status, book a follow-up appointment, and ask about required documents — all in one call.

Key design decisions:
- **Graph-based architecture** over linear chains — allows conditional branching, parallel tool calls, and dynamic re-routing based on conversation state
- **State persistence** across turns — MemorySaver checkpointer keyed by conversation_id, the agent remembers everything from the current call without redundant re-processing
- **Streaming responses** to ElevenLabs — token-by-token SSE output to minimize perceived latency and keep the conversation feeling natural
- **Buffer words** — "Bir saniye bakiyorum... " sent before LangGraph starts processing, keeping the conversation natural during 1-3s LLM response time
- **Deterministic tool chaining** — status "additional_docs_needed" auto-triggers document lookup, "rejected" auto-generates appeal guidance. This is what ElevenLabs native agents can't guarantee
- **System tool calls** — escalate node returns `transfer_to_number` in OpenAI function call format, ElevenLabs executes the actual phone transfer

### 3. Secure Caller Authentication
Citizens must verify their identity before accessing personal information. The system supports two authentication methods:
- **TC Kimlik (National ID)** + Date of Birth — primary method with checksum validation
- **Application Reference Number** + Last Name — secondary method

The authentication flow follows ElevenLabs' best practices for secure caller identity verification, including progressive retry guidance, maximum attempt limits, and automatic escalation to human agents on repeated failures. The agent never reads back sensitive information like full ID numbers. KVKK (Turkish GDPR) compliant — PII redaction in all logs, TC Kimlik stored as SHA-256 hash, audit trail with no raw PII.

### 4. Graceful Degradation
The system degrades gracefully across three levels, ensuring citizens always get some level of service:

| Level | Condition | Behavior |
|-------|-----------|----------|
| 0 — Healthy | Normal operation | Full LangGraph agent with all nodes and tool chaining |
| 1 — Degraded | 3 consecutive LangGraph failures | Circuit breaker opens, direct OpenAI call with system prompt (bypass graph). Auto-retries after 60s cooldown |
| 2 — Down | Custom LLM server unreachable | ElevenLabs falls back to native LLM via backup_llm_config |

The `/health` endpoint reports current degradation level and consecutive failure count for monitoring.

### 5. RAG Knowledge Base (planned)
A retrieval-augmented generation pipeline that gives the agent access to government service documentation. Built with Pinecone vector store and OpenAI embeddings.

Coverage includes:
- Frequently asked questions across 5+ service categories
- Service eligibility requirements and required documents
- Office hours, locations, and fee schedules
- Step-by-step application procedures

All documents exist in both Turkish and English with metadata filtering to ensure language-appropriate retrieval. The agent cites its sources and refuses to answer beyond what the knowledge base contains — no hallucination.

### 6. Mock Government API
A FastAPI-based simulation of real government backend systems. Provides endpoints for:
- **Identity verification** — validates caller credentials against citizen database (TC Kimlik checksum + DB lookup, or app ref + last name)
- **Handoff** — records escalation context when transferring to human operator
- **Guest info** — FAQ access for unauthenticated callers

Populated with 23 realistic sample records covering various application stages (pending, in review, approved, rejected, additional documents needed).

### 7. Analytics Dashboard (planned)
A Streamlit-based monitoring dashboard that provides real-time visibility into agent performance. Tracks:
- **Call analytics** — volume, duration, resolution rate, first-call resolution
- **Authentication metrics** — success rate, average attempts, failure reasons
- **Intent distribution** — which services citizens ask about most
- **Language analytics** — Turkish vs English usage, language switching patterns
- **Anomaly detection** — flags unusual patterns in call volume, failure rates, or latency

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Voice Interface | ElevenLabs Conversational AI | Industry-leading voice quality, multilingual support, Custom LLM integration |
| Agent Framework | LangGraph | Stateful graph-based workflows, better than linear chains for complex multi-step conversations |
| LLM | OpenAI GPT-4o-mini | Reliable function calling, strong multilingual performance, fast for intent classification |
| Voice-Agent Bridge | FastAPI | Async streaming support, low latency, lightweight |
| Vector Database | Pinecone (planned) | Managed service, metadata filtering, fast semantic search |
| Embeddings | OpenAI text-embedding-3-small (planned) | Good balance of quality and cost for multilingual documents |
| Database | SQLite (demo) / PostgreSQL (production) | SQLAlchemy ORM for easy migration between demo and production |
| Dashboard | Streamlit (planned) | Fast to build, good enough for monitoring, familiar to data teams |

## Conversation Flow Example

```
Citizen: (calls in)

Agent:    Merhaba, Vatandas Hizmetleri'ne hosgeldiniz. Size nasil 
          yardimci olabilirim?

Citizen:  Basvurumun durumunu ogrenmek istiyorum.

Agent:    Tabii, basvuru durumunuzu kontrol edebilirim. Oncelikle 
          kimliginizi dogrulamam gerekiyor. TC Kimlik numaranizi 
          soyleyebilir misiniz?

Citizen:  12345678901

Agent:    Tesekkurler. Dogum tarihinizi de alabilir miyim?

Citizen:  15 Mart 1990

Agent:    Kimliginiz dogrulandi. Hosgeldiniz Ahmet Bey. Basvuru 
          numaraniz 2024-TR-4521, surecte "Incelemede" asamasinda. 
          Tahmini tamamlanma tarihi 15 Nisan. Baska bir konuda 
          yardimci olabilir miyim?

Citizen:  Evet, bir de randevu almak istiyorum.

Agent:    Tabii, hangi hizmet icin randevu almak istersiniz?

Citizen:  Pasaport yenileme.

Agent:    Pasaport yenileme icin en yakin musait tarih 18 Nisan 
          Persembe saat 10:00. Uygun mu?

Citizen:  Evet, olur.

Agent:    Randevunuz olusturuldu. 18 Nisan Persembe saat 10:00, 
          Kadikoy Nufus Mudurlugu. Bugunku gorusmemizde basvuru 
          durumunuzu kontrol ettik ve pasaport yenileme randevunuzu 
          olusturduk. Baska bir sorunuz var mi?

Citizen:  Yok, tesekkurler.

Agent:    Rica ederim, iyi gunler!
```

## Enterprise Scalability Considerations

This is a demo, but the architecture is designed with production deployment in mind:

- **Multi-region voice deployment** — ElevenLabs supports global edge deployment for low-latency voice in any region
- **Horizontal scaling** — FastAPI backend and LangGraph agent are stateless per-request, can scale behind a load balancer
- **Knowledge base updates** — re-indexing pipeline allows document updates without downtime
- **Multi-tenant architecture** — the same system can serve multiple government agencies with isolated knowledge bases and authentication backends
- **Compliance** — authentication flow designed for sensitive data handling, agent never stores or repeats full credentials
- **Observability** — all calls, tool invocations, and errors are logged for audit trails and continuous improvement

## What This Demonstrates

For ElevenLabs specifically, this project shows:

1. **Custom LLM integration** — not just using the default agent, but connecting a sophisticated LangGraph backend via Custom LLM endpoint with SSE streaming, buffer words, and system tool forwarding
2. **Enterprise use case thinking** — government services is a massive, underserved market for voice AI (see: ElevenLabs for Government + Ukraine deployment)
3. **Security-first design** — caller authentication is a core concern, not an afterthought. KVKK compliance, PII redaction, audit trails
4. **Full-stack ownership** — voice layer, agent logic, API integrations, knowledge base, and analytics dashboard — all built end-to-end
5. **Multilingual capability** — Turkish + English with architecture ready for more languages
6. **Production resilience** — graceful degradation across 3 levels, circuit breaker pattern, health monitoring endpoint
7. **Measurable impact framing** — the dashboard doesn't just show vanity metrics, it tracks resolution rate, authentication success, and anomaly detection — the metrics an enterprise customer would care about

## Getting Started

### Prerequisites
- Python 3.11+
- An [ElevenLabs](https://elevenlabs.io) account with Conversational AI access
- An [OpenAI](https://platform.openai.com) API key

### Setup

```bash
git clone https://github.com/Automaticare/Government-Citizen-Services-Voice-Agent.git
cd Government-Citizen-Services-Voice-Agent

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Fill in your API keys — see .env.example for required variables
```

### Run

```bash
# Seed the citizen database (23 sample records)
python -m api.seed_data

# Start the Government Backend API (port 8001)
uvicorn api.server:app --reload --port 8001

# Start the Custom LLM server (port 8000) — LangGraph proxy for ElevenLabs
uvicorn agent.server:app --reload --port 8000

# Deploy agent to ElevenLabs (set CUSTOM_LLM_URL for voice integration)
python -m agent.deploy --dry-run        # Preview config
python -m agent.deploy                  # Deploy to platform

# Run tests
python -m pytest tests/ -v
```

## Project Structure

```
Government-Citizen-Services-Voice-Agent/
├── agent/                             # LangGraph agent core
│   ├── config.py                      # AgentConfig dataclass (API keys, custom LLM URL)
│   ├── deploy.py                      # Deploy agent to ElevenLabs (Custom LLM + backup LLM)
│   ├── graph.py                       # LangGraph StateGraph definition (8 nodes)
│   ├── logging_config.py              # PII redaction logging (KVKK compliance)
│   ├── server.py                      # Custom LLM proxy — SSE streaming, buffer words, circuit breaker
│   ├── state.py                       # AgentState TypedDict
│   ├── nodes/                         # Graph node implementations
│   │   ├── intent_classify.py         # LLM-based intent classification (7 intents)
│   │   ├── service_router.py          # Conditional routing to service nodes
│   │   ├── status_check.py            # Application status + deterministic tool chaining
│   │   ├── appointment_book.py        # Appointment booking
│   │   ├── document_request.py        # Document request processing
│   │   ├── faq_answer.py              # FAQ / general questions (RAG via Pinecone planned)
│   │   ├── complaint.py               # Complaint recording
│   │   ├── escalate.py                # Human transfer — transfer_to_number system tool call
│   │   └── utils.py                   # Shared node utilities (mark_completed)
│   ├── prompts/                       # Versioned system prompts
│   │   ├── loader.py                  # Prompt loader with version management
│   │   └── v1.0/                      # Current prompt version
│   │       ├── system_prompt_tr.md    # Turkish system prompt
│   │       └── system_prompt_en.md    # English system prompt
│   └── tools/                         # Validators
│       ├── tc_kimlik.py               # TC Kimlik checksum validator + masking
│       └── app_ref.py                 # Application reference format validator
├── api/                               # Government backend (FastAPI, port 8001)
│   ├── server.py                      # FastAPI app with auth + handoff routes
│   ├── auth.py                        # POST /auth/verify/tc-kimlik, /auth/verify/app-ref
│   ├── handoff.py                     # POST /handoff, POST /guest/info
│   ├── models.py                      # SQLAlchemy models (Citizen, AuthAuditLog)
│   └── seed_data.py                   # 23 citizen records seeder
├── dashboard/                         # Streamlit analytics app (planned)
├── data/                              # citizens.db — SQLite (gitignored)
├── docs/
│   ├── auth_flow.md                   # Authentication state diagram
│   └── conversation_flow.md           # Conversation flow documentation
├── tests/                             # 116 tests
│   ├── conftest.py                    # Shared test DB setup, per-test audit log cleanup
│   ├── test_agent_connection.py       # Agent config & Custom LLM config tests
│   ├── test_auth.py                   # Authentication flow tests (20 tests)
│   ├── test_graph.py                  # Graph nodes, routing, SSE proxy, circuit breaker
│   ├── test_handoff.py                # Handoff endpoint tests
│   ├── test_intent_detection.py       # ElevenLabs simulation API intent tests
│   ├── test_language_detection.py     # Language switching simulation tests
│   ├── test_logging.py                # PII redaction filter tests
│   ├── test_tc_kimlik.py              # TC Kimlik validator tests
│   └── eval/                          # Automated conversation evaluation (planned)
├── .env.example                       # Required environment variables
├── .gitignore
├── CLAUDE.md                          # Development guidelines
├── Makefile                           # make test, make test-live, make deploy
├── requirements.txt                   # Python dependencies
├── readme.md                          # This file
└── issues.md                          # Roadmap and issue tracking
```

## References

- [ElevenLabs Forward Deployed Engineers](https://elevenlabs.io/blog/forward-deployed-engineers)
- [Practical Guide: Open Source Agent Frameworks + ElevenAgents](https://elevenlabs.io/blog/practical-guide-open-source-agent-frameworks-and-elevenagents)
- [Unpacking ElevenAgents Orchestration Engine](https://elevenlabs.io/blog/unpacking-elevenagents-orchestration-engine)
- [Designing Secure Caller Identity Authentication Flows](https://elevenlabs.io/blog/designing-secure-caller-identity-authentication-flows-for-voice-agents)
- [ElevenLabs for Government](https://elevenlabs.io/blog/introducing-elevenlabs-for-government)

## Author

**Umut Dincer Yananer**
[LinkedIn](https://linkedin.com/in/umut-yananer) | [GitHub](https://github.com/Automaticare) | [Website](https://yananer.dev)
