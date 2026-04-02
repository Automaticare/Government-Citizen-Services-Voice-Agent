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
│              │     │                  │     │  │ Language Detect   │   │
└──────────────┘     │  - STT (Speech   │     │  │ Intent Classify   │   │
                     │    to Text)      │     │  │ Authenticate      │   │
                     │  - TTS (Text     │     │  │ Service Router    │   │
                     │    to Speech)    │     │  │ Status Check      │   │
                     │  - Voice Models  │     │  │ Appointment Book  │   │
                     │    (TR + EN)     │     │  │ FAQ Answer        │   │
                     └──────────────────┘     │  │ Escalate          │   │
                              ▲               │  └──────────────────┘   │
                              │               └────────┬───┬───┬────────┘
                     Custom LLM Endpoint               │   │   │
                     (FastAPI + Streaming)              │   │   │
                                                       │   │   │
                              ┌─────────────────────────┘   │   └────────────────────┐
                              │                             │                        │
                              ▼                             ▼                        ▼
                     ┌────────────────┐          ┌──────────────────┐      ┌──────────────────┐
                     │  Mock Gov API  │          │    Pinecone      │      │   Streamlit      │
                     │  (FastAPI)     │          │    Vector Store   │      │   Dashboard      │
                     │                │          │                  │      │                  │
                     │ - /applications│          │  - Gov FAQs      │      │ - Call Volume    │
                     │ - /appointments│          │  - Regulations   │      │ - Auth Metrics   │
                     │ - /documents   │          │  - Procedures    │      │ - Intent Dist.   │
                     │ - /auth/verify │          │  - TR + EN docs  │      │ - Anomaly Detect │
                     └────────────────┘          └──────────────────┘      └──────────────────┘
```

## Core Components

### 1. ElevenLabs Voice Layer
The voice interface that citizens interact with. Handles speech-to-text, text-to-speech, and voice model selection. Supports Turkish and English with automatic language detection and dynamic voice switching. Connected to our custom LLM backend via ElevenLabs' Custom LLM endpoint.

### 2. LangGraph Agent (Custom LLM)
The brain of the system. A stateful, multi-step agent built with LangGraph that manages the entire conversation flow. Unlike a simple prompt-response chatbot, this agent maintains conversation state, makes autonomous decisions about which tools to call, and handles complex multi-intent conversations where a citizen might check their application status, book a follow-up appointment, and ask about required documents — all in one call.

Key design decisions:
- **Graph-based architecture** over linear chains — allows conditional branching, parallel tool calls, and dynamic re-routing based on conversation state
- **State persistence** across turns — the agent remembers everything from the current call without redundant re-processing
- **Streaming responses** to ElevenLabs — token-by-token output to minimize perceived latency and keep the conversation feeling natural

### 3. Secure Caller Authentication
Citizens must verify their identity before accessing personal information. The system supports two authentication methods:
- **TC Kimlik (National ID)** + Date of Birth — primary method with checksum validation
- **Application Reference Number** + Last Name — secondary method

The authentication flow follows ElevenLabs' best practices for secure caller identity verification, including progressive retry guidance, maximum attempt limits, and automatic escalation to human agents on repeated failures. The agent never reads back sensitive information like full ID numbers.

### 4. RAG Knowledge Base
A retrieval-augmented generation pipeline that gives the agent access to government service documentation. Built with Pinecone vector store and OpenAI embeddings.

Coverage includes:
- Frequently asked questions across 5+ service categories
- Service eligibility requirements and required documents
- Office hours, locations, and fee schedules
- Step-by-step application procedures

All documents exist in both Turkish and English with metadata filtering to ensure language-appropriate retrieval. The agent cites its sources and refuses to answer beyond what the knowledge base contains — no hallucination.

### 5. Mock Government API
A FastAPI-based simulation of real government backend systems. Provides endpoints for:
- **Application status lookup** — returns current stage, estimated completion, notes
- **Appointment booking** — accepts preferred date/service, returns confirmation
- **Document requests** — initiates document preparation with estimated delivery
- **Identity verification** — validates caller credentials against citizen database

Populated with 20+ realistic sample records covering various application stages (pending, in review, approved, rejected, additional documents needed).

### 6. Analytics Dashboard
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
| LLM | OpenAI GPT-4 | Reliable function calling, strong multilingual performance |
| Voice-Agent Bridge | FastAPI | Async streaming support, low latency, lightweight |
| Vector Database | Pinecone | Managed service, metadata filtering, fast semantic search |
| Embeddings | OpenAI text-embedding-3-small | Good balance of quality and cost for multilingual documents |
| Mock Backend | FastAPI | Consistent with the bridge server, easy to extend |
| Database | PostgreSQL | Reliable, extensible, production-standard |
| Dashboard | Streamlit | Fast to build, good enough for monitoring, familiar to data teams |
| Monitoring | Streamlit + custom logging | Lightweight observability without infrastructure overhead |

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

1. **Custom LLM integration** — not just using the default agent, but connecting a sophisticated LangGraph backend via Custom LLM endpoint
2. **Enterprise use case thinking** — government services is a massive, underserved market for voice AI (see: ElevenLabs for Government + Ukraine deployment)
3. **Security-first design** — caller authentication is a core concern, not an afterthought
4. **Full-stack ownership** — voice layer, agent logic, API integrations, knowledge base, and analytics dashboard — all built end-to-end
5. **Multilingual capability** — Turkish + English with architecture ready for more languages
6. **Measurable impact framing** — the dashboard doesn't just show vanity metrics, it tracks resolution rate, authentication success, and anomaly detection — the metrics an enterprise customer would care about

## Getting Started

```bash
git clone https://github.com/Automaticare/Government-Citizen-Services-Voice-Agent.git
cd Government-Citizen-Services-Voice-Agent

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Fill in your API keys: ELEVENLABS_API_KEY, PINECONE_API_KEY, OPENAI_API_KEY

# Start the Custom LLM server
uvicorn agent.server:app --reload --port 8000

# Start the Mock Government API
uvicorn api.government:app --reload --port 8001

# Start the Dashboard
streamlit run dashboard/app.py
```

## Project Structure

```
Government-Citizen-Services-Voice-Agent/
├── agent/
│   ├── server.py              # FastAPI Custom LLM endpoint
│   ├── graph.py               # LangGraph workflow definition
│   ├── nodes/                 # Individual graph nodes
│   │   ├── language_detect.py
│   │   ├── intent_classify.py
│   │   ├── authenticate.py
│   │   ├── service_router.py
│   │   ├── status_check.py
│   │   ├── appointment_book.py
│   │   ├── faq_answer.py
│   │   └── escalate.py
│   ├── tools/                 # Tool definitions and schemas
│   ├── prompts/               # System prompts (TR + EN)
│   └── state.py               # LangGraph state schema
├── api/
│   ├── government.py          # Mock government API
│   ├── models.py              # Data models
│   └── seed_data.py           # Sample citizen/application data
├── rag/
│   ├── embed.py               # Embedding pipeline
│   ├── retriever.py           # Pinecone retrieval logic
│   └── chunker.py             # Document chunking
├── dashboard/
│   ├── app.py                 # Streamlit main app
│   ├── pages/                 # Dashboard pages
│   └── components/            # Reusable chart components
├── data/
│   ├── knowledge_base/        # Government service documents (TR + EN)
│   └── citizens.json          # Mock citizen database
├── tests/
│   ├── test_nodes/            # Unit tests per node
│   ├── test_tools/            # Tool integration tests
│   ├── test_auth/             # Authentication flow tests
│   └── test_e2e/              # End-to-end scenario tests
├── docs/
│   ├── ARCHITECTURE.md        # Detailed system design
│   ├── DECISIONS.md           # Design decisions and tradeoffs
│   └── diagrams/              # Architecture and flow diagrams
├── .env.example
├── requirements.txt
├── README.md                  # This file
└── SUMMARY.pdf                # 1-page executive summary
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