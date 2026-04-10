# Design Decisions

Key architectural decisions, tradeoffs, and rationale for the Government Citizen Services Voice Agent.

## 1. ElevenLabs Workflow for Auth, LangGraph for Intelligence

**Decision:** Use ElevenLabs Workflow engine for authentication gating (deterministic dispatch tool), and LangGraph for post-auth service intelligence (intent classification, tool chaining, RAG).

**Why not just LangGraph for everything?**
Authentication requires a deterministic yes/no decision — not LLM inference. ElevenLabs' dispatch tool calls our webhook, gets a boolean result, and routes to the correct subagent. This can't hallucinate or get confused. LLM-based auth gating would risk false positives.

**Why not just ElevenLabs native for everything?**
ElevenLabs native agents can't guarantee deterministic tool chaining. When a status check returns "additional_docs_needed", we need to *automatically* query the knowledge base for required documents. Native agents might do this, or might just say "you need more documents" without looking them up. LangGraph makes this programmatic.

**Tradeoff:** Two systems to maintain. But each does what it's best at.

## 2. Stateless Message Passing (No Checkpointer)

**Decision:** No server-side state persistence between turns. ElevenLabs sends full conversation history with every request.

**Why:** ElevenLabs' Custom LLM protocol sends all messages each turn. Maintaining a parallel state store would create consistency issues — what if ElevenLabs' history and our checkpointer diverge? Simpler to be stateless and trust the platform.

**Tradeoff:** Can't persist structured data between turns (e.g., "remember that status_check found rejected status"). But conversation history contains this information in text form, and intent_classify reads the full history.

## 3. GPT-4o for All LangGraph Nodes

**Decision:** Upgraded all nodes from GPT-4o-mini to GPT-4o.

**Why:** GPT-4o-mini struggled with:
- Intent classification from ambiguous Turkish/English messages
- Understanding conversation context for follow-up requests
- Generating natural, TTS-friendly responses

GPT-4o costs more but the quality difference in a voice agent context (where every response is spoken aloud) justified the upgrade.

**Tradeoff:** Higher cost per request. Acceptable for demo; production would benchmark both.

## 4. GPT-4o for Service Router (Not Custom LLM)

**Decision:** The ElevenLabs Workflow Service Router node uses GPT-4o (native), not Custom LLM.

**Why:** When Service Router uses Custom LLM, the workflow edge conditions (LLM conditions like "user wants to check status") don't trigger — ElevenLabs can't evaluate conditions on Custom LLM responses the same way it can on native LLM responses. This is a platform limitation discovered during testing.

**Tradeoff:** Service Router doesn't benefit from LangGraph intelligence. But its job is simple routing — it just needs to understand what the user wants and let the workflow edges handle the transition.

## 5. STT-Friendly Authentication (Last 4 Digits)

**Decision:** Authenticate with last 4 digits of TC Kimlik + date of birth + father's name initial, instead of full 11-digit ID number.

**Why:** Dictating an 11-digit number over voice is error-prone. STT systems frequently misrecognize digits, especially in sequences. Last 4 digits + two other factors provides equivalent security with much better voice UX.

**Tradeoff:** Slightly weaker uniqueness (10,000 possible last-4 combinations vs 10 billion full numbers). Mitigated by requiring DOB + father initial as additional factors.

## 6. Sentence-Level SSE Streaming

**Decision:** Split LangGraph responses by sentence boundaries and stream with 80ms delays between sentences.

**Why:** ElevenLabs TTS processes text as it arrives. If we send the entire response at once, TTS starts speaking before the full context is available, potentially causing unnatural pauses. Sentence-by-sentence streaming mimics real LLM token streaming and gives TTS time to buffer naturally.

**Tradeoff:** Slightly slower time-to-first-byte compared to sending everything at once. But the perceived naturalness is much better.

## 7. Full History for Intent Classification

**Decision:** intent_classify receives the full filtered conversation history (system messages excluded), not just the last message.

**Why:** Without history, follow-up requests fail. If a user says "the passport one" after seeing a list of applications, the LLM needs to see the previous listing to understand this refers to a passport application. Also enables topic change detection — "forget about that, I want to book an appointment."

**Tradeoff:** More tokens per classification call. But intent_classify runs once per turn and the improved accuracy is worth the cost.

## 8. [NODE:xxx] Markers for Workflow-LangGraph Coordination

**Decision:** Each ElevenLabs Workflow subagent node includes a `[NODE:xxx]` marker in its additional prompt. server.py parses this to tell LangGraph which workflow node is active.

**Why:** ElevenLabs doesn't expose the current workflow node name via API. The marker is a simple, reliable coordination mechanism. LangGraph always runs intent_classify regardless (to handle topic changes), but the marker provides context.

**Tradeoff:** Coupling between dashboard configuration and server.py regex. If someone removes the marker, LangGraph falls back to intent-only routing — still works, just without workflow context.

## 9. Pre-Auth FAQ via Native KB, Post-Auth via Custom LLM

**Decision:** General FAQ (working hours, fees, required documents) uses ElevenLabs' native knowledge base. Post-auth operations (status check, appointments) use Custom LLM / LangGraph.

**Why:** This demonstrates platform mastery — using native features where they're sufficient, and Custom LLM where deterministic control is needed. Native KB is faster (no server round-trip) and works even if our server is down (Level 2 degradation).

**Tradeoff:** FAQ content exists in two places (ElevenLabs KB + Pinecone). But they serve different purposes — native KB for pre-auth, Pinecone for post-auth tool chaining (status_check → RAG).

## 10. Single Server Architecture

**Decision:** One FastAPI server (port 8080) serves both the Custom LLM proxy (`/v1/chat/completions`) and the government API endpoints (`/auth/*`, `/applications/*`, etc.).

**Why:** During early development, LangGraph nodes called the government API via HTTP. Having two servers meant managing two processes, two ngrok tunnels, and cross-server latency. Mounting the API into the same server eliminated self-referencing HTTP deadlocks and simplified deployment.

**Tradeoff:** Less separation of concerns. In production, these would be separate services behind a load balancer.

## 11. Dynamic Variables for Auth State Persistence

**Decision:** After successful auth, citizen info (`first_name`, `citizen_id`, `application_ref`) is injected into the system prompt via ElevenLabs dynamic variables. server.py parses these every turn.

**Why:** Stateless architecture means we can't store auth state server-side. Dynamic variables are injected by ElevenLabs into every subsequent system prompt, so server.py can extract them each turn to maintain the "authenticated" state.

**Tradeoff:** Regex parsing of system prompt content. If ElevenLabs changes the format, parsing breaks. But it's simple and reliable for the demo scope.

## 12. Circuit Breaker over Retry Logic

**Decision:** After 3 consecutive LangGraph failures, open the circuit breaker and fall back to direct OpenAI calls. Don't retry the same failing path.

**Why:** In a voice call, the user is waiting in real-time. Retrying a failing LangGraph graph 3 times would add seconds of dead air. Better to immediately fall back to a simpler (but functional) response path. Auto-recovery after 60s cooldown.

**Tradeoff:** Level 1 degradation loses tool chaining and structured responses. But the citizen still gets an answer, which is better than silence.

## 13. Gender-Based Honorifics from DB Lookup

**Decision:** Look up citizen gender from database when building honorific names, rather than adding it as an ElevenLabs dynamic variable.

**Why:** Adding `gender` as a dynamic variable would require changing the ElevenLabs dispatch tool configuration. DB lookup on `citizen_id` (which we already have from dynamic variables) is simpler and doesn't touch the platform configuration.

**Tradeoff:** Extra DB query per request. But it's a simple primary key lookup — negligible latency.
