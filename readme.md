# Government Citizen Services Voice Agent

An AI-powered multilingual voice agent that enables citizens to access government services through natural phone conversations. Built on ElevenLabs Conversational AI with a custom LangGraph-based agent backend, RAG-powered knowledge retrieval, and real-time analytics dashboard.

## The Problem

Government call centers are overwhelmed. The US Social Security Administration handles **93.5 million calls per year** with average wait times reaching **99 minutes** ([ssa.gov](https://www.ssa.gov/data/800-number-call-volume-and-agent-busy-rate.html)). UK's HMRC receives over **38 million calls annually** with only 71.5% answered ([gov.uk](https://www.gov.uk/government/publications/hmrc-annual-report-and-accounts-2024-to-2025)). The US federal government spent **$4 billion on call center contracts** over five years ([GAO-20-291](https://www.gao.gov/products/gao-20-291)). The vast majority of these calls are routine — application status, appointment scheduling, document requests — interactions that don't require human judgment but keep citizens waiting.

## The Solution

This project builds an always-on voice agent that handles citizen inquiries autonomously through natural conversation. Citizens call in, authenticate securely, and get immediate answers — whether they're checking an application status, booking an appointment, or asking about required documents. The agent speaks English and Turkish, authenticates callers securely, retrieves answers from an official knowledge base, takes real actions (booking, document requests), and escalates to humans when needed.

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│              │     │                  │     │    LangGraph Agent       │
│   Citizen    │────>│   ElevenLabs     │────>│                         │
│   (Phone)    │<────│   Voice Layer    │<────│  ┌──────────────────┐   │
│              │     │                  │     │  │ Intent Classify   │   │
└──────────────┘     │  - STT (Speech   │     │  │ Service Router    │   │
                     │    to Text)      │     │  │ Status Check      │   │
                     │  - TTS (Text     │     │  │ Appointment Book  │   │
                     │    to Speech)    │     │  │ Appointment List  │   │
                     │  - Workflow      │     │  │ Appointment Cancel│   │
                     │    (Auth Gate)   │     │  │ Document Request  │   │
                     │  - Language      │     │  │ Document Status   │   │
                     │    Detection     │     │  │ FAQ Answer (RAG)  │   │
                     └──────────────────┘     │  │ Complaint         │   │
                              ▲               │  │ Escalate          │   │
                     Custom LLM Endpoint      │  └──────────────────┘   │
                     (FastAPI + SSE)           └────────┬───┬───┬────────┘
                                                       │   │   │
                              ┌─────────────────────────┘   │   └────────────────────┐
                              │                             │                        │
                              ▼                             ▼                        ▼
                     ┌────────────────┐          ┌──────────────────┐      ┌──────────────────┐
                     │  Gov Backend   │          │    Pinecone      │      │   Streamlit      │
                     │  (FastAPI)     │          │    Vector Store  │      │   Dashboard      │
                     │                │          │                  │      │   (9 pages)      │
                     │ - /auth/verify │          │  - Gov KB        │      │                  │
                     │ - /applications│          │    (40 docs)     │      │ - Overview       │
                     │ - /appointments│          │  - ElevenLabs    │      │ - Intents        │
                     │ - /documents   │          │    Docs (514     │      │ - Auth & Lang    │
                     │ - /services    │          │    chunks)       │      │ - Knowledge Gaps │
                     │ - /handoff     │          │                  │      │ - Conv. Flows    │
                     │ - Citizen DB   │          │                  │      │ - Node Details   │
                     └────────────────┘          └──────────────────┘      │ - System Health  │
                                                                          │ - AI Insights    │
                                                                          │ - Logs           │
                                                                          └──────────────────┘
```

For a detailed architecture breakdown with sequence diagrams, see [ARCHITECTURE.md](docs/ARCHITECTURE.md).
For key design decisions and tradeoffs, see [DECISIONS.md](docs/DECISIONS.md).

## Core Components

### 1. ElevenLabs Voice Layer
The voice interface that citizens interact with. Handles speech-to-text, text-to-speech, and voice model selection. Supports English and Turkish with automatic language detection and dynamic voice switching. Connected to our custom LLM backend via ElevenLabs' Custom LLM endpoint.

Key platform-native features used:
- **Workflow engine** — deterministic auth gating via dispatch tool + subagent isolation (not LLM-based)
- **Language detection** — system tool that auto-detects caller language and switches voice model
- **Language presets** — single agent with EN primary + TR preset, one endpoint for both languages
- **Native knowledge base** — pre-auth FAQ handled by ElevenLabs KB (no Custom LLM needed)
- **Backup LLM** — if our Custom LLM server is unreachable, ElevenLabs falls back to its native LLM (Level 2 graceful degradation)

### 2. LangGraph Agent (Custom LLM)
The brain of the system. A multi-step agent built with LangGraph that manages the entire post-auth conversation flow. Unlike a simple prompt-response chatbot, this agent classifies intent from full conversation history, makes autonomous decisions about which tools to call, and handles complex multi-intent conversations where a citizen might check their application status, book a follow-up appointment, and request a document — all in one call.

Key capabilities:
- **11-node graph** — intent_classify, service_router, status_check, appointment_book/list/cancel, document_request/status, faq_answer, complaint, escalate
- **Deterministic tool chaining** — status "additional_docs_needed" auto-triggers RAG document lookup, "rejected" auto-generates appeal guidance. This is what ElevenLabs native agents can't guarantee
- **Stateless message passing** — ElevenLabs sends full conversation history each turn, no server-side persistence needed
- **Sentence-level SSE streaming** — responses split by sentence with delays for natural TTS delivery
- **Smart service detection** — detects service type and document type from conversation context, asks clarifying questions when ambiguous
- **Gender-based honorifics** — "Mr. John" / "Ms. Sarah" in English, "Ahmet Bey" / "Fatma Hanim" in Turkish

### 3. Secure Caller Authentication
Citizens must verify their identity before accessing personal information. The system uses an STT-friendly approach:
- **Last 4 digits** of TC Kimlik (National ID) — not the full 11-digit number
- **Date of birth** — day, month, year
- **Father's name initial** — single letter

The authentication flow follows ElevenLabs' Workflow best practices for secure caller identity verification: deterministic dispatch tool (webhook) routes to authenticated or retry subagent based on boolean result — no LLM inference involved in the auth decision. KVKK (Turkish GDPR) compliant — PII redaction in all logs, TC Kimlik stored as SHA-256 hash, audit trail with no raw PII.

### 4. Graceful Degradation
The system degrades gracefully across three levels, ensuring citizens always get some level of service:

| Level | Condition | Behavior |
|-------|-----------|----------|
| 0 — Healthy | Normal operation | Full LangGraph agent with all nodes and tool chaining |
| 1 — Degraded | 3 consecutive LangGraph failures | Circuit breaker opens, direct OpenAI call (bypass graph). Auto-retries after 60s cooldown |
| 2 — Down | Custom LLM server unreachable | ElevenLabs falls back to native LLM via backup_llm_config |

The `/health` endpoint reports current degradation level and consecutive failure count for monitoring.

### 5. RAG Knowledge Base
A retrieval-augmented generation pipeline that gives the agent access to government service documentation:
- **40 documents** across 5 categories (passport, ID card, driver's license, civil registry, general) x 4 doc types x 2 languages
- **219 chunks** embedded via OpenAI text-embedding-3-small into Pinecone serverless index
- **514 ElevenLabs documentation chunks** in a separate Pinecone index for platform-aware AI insights

Pre-auth FAQ handled by ElevenLabs native knowledge base (platform mastery). Post-auth tool chaining uses Pinecone for context-aware retrieval (status_check → RAG for required docs / appeal rights).

### 6. Mock Government API
A FastAPI-based simulation of real government backend systems with full CRUD operations:
- **7 API endpoints** — application status, appointment booking/listing/cancellation, document request/status, service catalog
- **23 citizens** with realistic data (Turkish + English names, multiple applications per citizen)
- **26 applications** across 4 service types and 5 statuses
- **5 appointments** and **3 document requests** as seed data
- **Conflict detection** — prevents duplicate appointments for the same service
- **Edge case handling** — past date rejection, slot availability checks

### 7. Analytics Dashboard
A 9-page Streamlit dashboard with sidebar navigation providing real-time visibility into agent performance:

| Page | What it shows |
|------|--------------|
| **Overview** | KPIs (total requests, conversations, avg response, resolution rate, escalation rate), call volume trends, turns per conversation |
| **Intents & Performance** | Intent distribution, per-intent response time, Min/P50/P95/Max latency, node-level timing breakdown |
| **Auth & Language** | Auth success rate, failure reasons, auth methods, language distribution |
| **Knowledge Gaps** | RAG score distribution, low-score queries, content improvement recommendations |
| **Conversation Flows** | Sankey diagram of intent transitions, most common paths, entry/exit points, conversation depth |
| **Node Details** | Per-node execution count and timing, tool chain analysis, API call volume by node |
| **System Health** | Anomaly detection (escalation spikes, latency, auth failures, volume), threshold monitoring |
| **AI Insights** | GPT-4o + ElevenLabs docs RAG powered recommendations |
| **Logs** | Recent conversation logs with all fields |

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Voice Interface | ElevenLabs Conversational AI | Industry-leading voice quality, Workflow engine, Custom LLM integration |
| Agent Framework | LangGraph | Stateful graph-based workflows — conditional branching, deterministic tool chaining |
| LLM | OpenAI GPT-4o | Strong multilingual performance, reliable intent classification |
| Voice-Agent Bridge | FastAPI | Async streaming support, low latency, SSE for ElevenLabs Custom LLM |
| Vector Database | Pinecone (Serverless) | Managed service, metadata filtering, fast semantic search |
| Embeddings | OpenAI text-embedding-3-small | Good balance of quality and cost for multilingual documents |
| Database | SQLite (demo) / PostgreSQL (production) | SQLAlchemy ORM for easy migration |
| Dashboard | Streamlit | Rapid development, plotly integration for Sankey diagrams |

## Conversation Flow Examples

### English

```
Citizen: (calls in)

Agent:    Hello, welcome to Citizen Services. I'm Umut, how can I 
          help you today?

Citizen:  I want to check my application status.

Agent:    I need to ask you three quick questions to verify your 
          identity. Could you please tell me the last four digits 
          of your ID number?

Citizen:  Zero zero one eight.

Agent:    Could you please tell me your date of birth?

Citizen:  March fifteenth, nineteen ninety.

Agent:    And the first letter of your father's name?

Citizen:  M.

Agent:    Verification complete. Mr. Ahmet, you have two applications
          on file. Your passport application is under review. Your 
          ID card application is approved. Which one would you like 
          more details about?

Citizen:  The passport one.

Agent:    Mr. Ahmet, your passport application is currently under 
          review. Biometric verification is complete. Estimated 
          completion is five to ten business days. Is there anything 
          else I can help you with?

Citizen:  Yes, I'd also like to book an appointment.

Agent:    Mr. Ahmet, which service would you like to book an 
          appointment for? Passport, ID card, driver's license, 
          or civil registry?

Citizen:  Driver's license.

Agent:    Mr. Ahmet, your driver's license appointment has been 
          booked. Date: April seventh, Time: ten AM, Location: 
          Kadikoy Office. Please bring your ID card and any 
          required documents.

Citizen:  That's all, thank you.

Agent:    You're welcome, have a great day!
```

### Turkish

```
Vatandas: (arar)

Ajan:     Merhaba, Vatandas Hizmetleri'ne hos geldiniz. Ben Umut, 
          size nasil yardimci olabilirim?

Vatandas: Basvurumun durumunu ogrenmek istiyorum.

Ajan:     Kimliginizi dogrulamam icin size uc kisa soru soracagim. 
          TC Kimlik numaranizin son dort hanesini soyler misiniz?

Vatandas: Sifir sifir bir sekiz.

Ajan:     Dogum tarihinizi gun, ay ve yil olarak soyler misiniz?

Vatandas: On bes Mart bin dokuz yuz doksan.

Ajan:     Baba adinizin ilk harfini soyler misiniz?

Vatandas: M.

Ajan:     Dogrulama tamamlandi. Ahmet Bey, sistemde iki basvurunuz
          bulunuyor. Pasaport basvurunuz incelemede. Kimlik karti 
          basvurunuz onaylandi. Hangisi hakkinda detayli bilgi almak
          istersiniz?

Vatandas: Pasaport.

Ajan:     Ahmet Bey, pasaport basvurunuz inceleme asamasindadir. 
          Biyometrik dogrulama tamamlandi. Tahmini tamamlanma suresi
          bes ila on is gunu. Baska bir konuda yardimci olabilir 
          miyim?

Vatandas: Evet, bir de randevu almak istiyorum.

Ajan:     Ahmet Bey, hangi hizmet icin randevu almak istiyorsunuz? 
          Pasaport, kimlik karti, ehliyet veya nufus islemi?

Vatandas: Ehliyet.

Ajan:     Ahmet Bey, ehliyet randevunuz olusturuldu. Tarih: yedi 
          Nisan, Saat: sabah on, Yer: Kadikoy Nufus Mudurlugu. 
          Lutfen nufus cuzdaninizi ve gerekli belgeleri yaninizda 
          getirin.

Vatandas: Baska bir sey yok, tesekkurler.

Ajan:     Rica ederim, iyi gunler!
```

## Market Context

Gartner predicts conversational AI will reduce contact center agent labor costs by **$80 billion in 2026** ([gartner.com](https://www.gartner.com/en/newsroom/press-releases/2022-08-31-gartner-predicts-conversational-ai-will-reduce-contac)). ElevenLabs signed an MoU with Ukraine's Ministry of Digital Transformation (September 2025) to integrate voice AI into the Diia government portal — serving **21+ million users** with **1.6 billion backend transactions** ([kmu.gov.ua](https://www.kmu.gov.ua/en/news/trembita-zdijsnila-ponad-16-mlrd-tranzakcij-mizh-derzhreyestrami)). Turkey's e-Devlet gateway serves **66.75 million registered users** (96% of population aged 15+) with **4.23 billion logins per year** ([turkiye.gov.tr](https://www.turkiye.gov.tr/edevlet-istatistikleri)) — voice AI is the natural next layer on top of this digital infrastructure.

## Enterprise Scalability Considerations

This is a demo, but the architecture is designed with production deployment in mind:

- **Multi-region voice deployment** — ElevenLabs supports global edge deployment for low-latency voice in any region
- **Horizontal scaling** — FastAPI backend and LangGraph agent are stateless per-request, can scale behind a load balancer
- **Knowledge base updates** — re-indexing pipeline allows document updates without downtime
- **Multi-tenant architecture** — the same system can serve multiple government agencies with isolated knowledge bases and authentication backends
- **Compliance** — CORS policy, security headers (OWASP), rate limiting, GDPR right to erasure, PII redaction, SHA-256 hashed credentials, audit trail. ElevenLabs platform holds SOC 2 Type II, ISO 27001, HIPAA, and GDPR certifications ([elevenlabs.io](https://compliance.elevenlabs.io/))
- **Observability** — ConversationLog tracks intent, timing, RAG scores, tool chains, and API calls per request

## What This Demonstrates

For ElevenLabs specifically, this project shows:

1. **Custom LLM integration** — not just using the default agent, but connecting a sophisticated LangGraph backend via Custom LLM endpoint with SSE streaming and system tool forwarding
2. **Workflow mastery** — deterministic auth gating via dispatch tool + subagent isolation, LLM condition edges for service routing, backward edges for auth retry
3. **Enterprise use case thinking** — government services is a massive, underserved market for voice AI
4. **Security-first design** — caller authentication is a core concern, not an afterthought. KVKK compliance, PII redaction, audit trails
5. **Full-stack ownership** — voice layer, agent logic, API integrations, knowledge base, analytics dashboard, and test suite — all built end-to-end
6. **Multilingual capability** — English + Turkish with architecture ready for more languages
7. **Production resilience** — graceful degradation across 3 levels, circuit breaker pattern, health monitoring
8. **Measurable analytics** — 9-page dashboard with Sankey flow visualization, node-level timing, tool chain analysis, knowledge gap detection

## Future Vision: Agentic Self-Improvement

The current system is a solid foundation. The next evolution is making it **self-improving** through multi-agent intelligence:

- **Multi-Agent Insight Engine** — specialized agents (RAG Quality Agent, Performance Agent, Pattern Agent, Platform Agent) that analyze conversation data and produce actionable, platform-aware recommendations with source data attribution
- **Sentiment Tracking** — per-conversation sentiment analysis to detect citizen satisfaction trends and correlate with specific intents or nodes
- **A/B Testing Framework** — compare prompt versions, LLM models, and conversation strategies with statistical significance tracking
- **Self-Improving Nodes** — each LangGraph node monitors its own performance metrics and automatically adjusts prompts, thresholds, or routing logic based on observed patterns
- **Predictive Analytics** — peak hour prediction and cost optimization based on historical call patterns

These features require production-level conversation volume to be meaningful and are designed to activate as data accumulates.

## Getting Started

### Prerequisites
- Python 3.11+
- An [ElevenLabs](https://elevenlabs.io) account with Conversational AI access
- An [OpenAI](https://platform.openai.com) API key
- A [Pinecone](https://pinecone.io) account (free tier)

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
# Seed the citizen database (23 citizens, 26 applications, 5 appointments, 3 doc requests)
python -m api.seed_data

# Start the server (single server — gov API mounted into agent server)
uvicorn agent.server:app --reload --port 8080

# Start ngrok tunnel (for ElevenLabs to reach our server)
ngrok http 8080

# Deploy agent to ElevenLabs (set CUSTOM_LLM_URL for voice integration)
CUSTOM_LLM_URL="https://your-ngrok-url.ngrok-free.dev" python -m agent.deploy
python -m agent.deploy --dry-run  # Preview config without deploying

# Run analytics dashboard
python -m streamlit run dashboard/app.py

# Run tests (231 tests)
python -m pytest tests/ -v
```

## Project Structure

```
Government-Citizen-Services-Voice-Agent/
├── agent/                             # LangGraph agent core
│   ├── config.py                      # AgentConfig dataclass (API keys, custom LLM URL)
│   ├── deploy.py                      # Deploy agent to ElevenLabs (EN primary + TR preset)
│   ├── graph.py                       # LangGraph StateGraph definition (11 nodes)
│   ├── logging_config.py              # PII redaction logging (KVKK compliance)
│   ├── server.py                      # Custom LLM proxy — SSE streaming, circuit breaker, analytics logging
│   ├── state.py                       # AgentState TypedDict (incl. node detail tracking)
│   ├── nodes/                         # Graph node implementations
│   │   ├── intent_classify.py         # LLM-based intent classification (10 intents, GPT-4o)
│   │   ├── service_router.py          # Context-aware response using conversation history
│   │   ├── status_check.py            # Application status + deterministic tool chaining (→ RAG)
│   │   ├── appointment_book.py        # Appointment booking with service type detection
│   │   ├── appointment_list.py        # List existing appointments
│   │   ├── appointment_cancel.py      # Cancel appointments with selection matching
│   │   ├── document_request.py        # Document request with type detection
│   │   ├── document_status.py         # Document request status listing
│   │   ├── faq_answer.py              # FAQ with RAG grounding (Pinecone) + edge case handling
│   │   ├── complaint.py               # Complaint recording with confirmation
│   │   ├── escalate.py                # Human transfer — empathetic message + operator summary
│   │   └── utils.py                   # Shared utilities (mark_completed, get_honorific)
│   ├── prompts/                       # Versioned system prompts
│   │   ├── loader.py                  # Prompt loader with version management
│   │   └── v1.0/                      # Current prompt version
│   │       ├── system_prompt_en.md    # English system prompt
│   │       └── system_prompt_tr.md    # Turkish system prompt
│   └── tools/                         # Validators + system tool schemas
│       ├── tc_kimlik.py               # TC Kimlik checksum validator + masking
│       ├── app_ref.py                 # Application reference format validator
│       ├── date_parser.py             # Multi-format date parser (voice-friendly)
│       └── schemas.py                 # ElevenLabs system tool configs (end_call, language_detection)
├── api/                               # Government backend (mounted into agent/server.py)
│   ├── server.py                      # Standalone FastAPI app (for independent testing)
│   ├── auth.py                        # Identity verification — webhook, TC Kimlik, app ref methods
│   ├── handoff.py                     # Escalation logging + guest mode FAQ
│   ├── services.py                    # Application, appointment, document, service catalog endpoints
│   ├── models.py                      # SQLAlchemy models (Citizen, Application, Appointment, DocumentRequest, ConversationLog, AuthAuditLog)
│   └── seed_data.py                   # 23 citizens + 26 applications + 5 appointments + 3 doc requests
├── rag/                               # RAG pipeline
│   ├── chunker.py                     # Document chunking (header-based + size overlap)
│   ├── embed.py                       # Gov KB embedding pipeline (OpenAI → Pinecone)
│   ├── embed_elevenlabs.py            # ElevenLabs docs embedding (514 chunks, separate index)
│   └── retriever.py                   # Pinecone query with language/category metadata filters
├── dashboard/                         # Streamlit analytics dashboard (9 pages)
│   ├── app.py                         # Multi-page dashboard with sidebar navigation
│   └── insights.py                    # LLM-powered recommendation engine (GPT-4o + RAG)
├── data/                              # citizens.db (SQLite, gitignored), knowledge_base/ (40 docs)
├── docs/
│   ├── ARCHITECTURE.md                # Detailed system design with diagrams
│   ├── DECISIONS.md                   # Key design decisions and tradeoffs
│   ├── auth_flow.md                   # Authentication state diagram
│   ├── conversation_flow.md           # Conversation flow documentation
│   └── langgraph_value.md             # LangGraph capabilities and voice test scenarios
├── tests/                             # 231 tests
│   ├── conftest.py                    # Shared test DB setup, per-test audit log cleanup
│   ├── test_core_system.py            # Comprehensive core system tests (104 tests, all product endings)
│   ├── test_auth.py                   # Authentication flow tests (20 tests)
│   ├── test_services.py               # Government API endpoint tests
│   ├── test_edge_cases.py             # TC Kimlik normalization, date parsing edge cases
│   ├── test_handoff.py                # Escalation and handoff tests
│   ├── test_schemas.py                # System tool schema tests
│   ├── test_logging.py                # PII redaction filter tests
│   ├── test_tc_kimlik.py              # TC Kimlik validator tests
│   ├── test_agent_connection.py       # Agent config and Custom LLM config tests
│   ├── test_intent_detection.py       # ElevenLabs simulation API intent tests
│   ├── test_language_detection.py     # Language switching simulation tests
│   ├── voice_e2e_test_roadmap.md      # 39 manual voice test scenarios
│   └── eval/                          # Automated conversation evaluation (planned)
├── .env.example                       # Required environment variables
├── .gitignore
├── CLAUDE.md                          # Development guidelines and project context
├── Makefile                           # make test, make test-live, make serve
├── requirements.txt                   # Python dependencies
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
