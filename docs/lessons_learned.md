# Lessons Learned

## ElevenLabs Custom LLM + Workflow Integration

### Problem
ElevenLabs Workflows use subagent nodes with edge conditions to control conversation flow. When using Custom LLM as the base agent, the interaction between workflow transitions and Custom LLM responses creates challenges.

### What We Tried and What Happened

#### 1. Collect Identity node = GPT-4o, Authenticated Service = Custom LLM
- **Result:** Auth flow worked (GPT-4o collected credentials, dispatch tool fired). But FAQ questions answered by GPT-4o without RAG — no knowledge base grounding.
- **Takeaway:** Workflow subagent LLM overrides completely replace the base agent LLM. If a node uses GPT-4o, Custom LLM is never called for that node.

#### 2. All nodes = Custom LLM (inherit from base)
- **Result:** FAQ + RAG worked. But auth flow broke — LangGraph classified each user response independently, losing multi-turn auth context.
- **Takeaway:** Custom LLM receives the full conversation history from ElevenLabs each turn, but our intent classifier only looked at the last message. Short responses like "0018" or "m" were classified as FAQ.

#### 3. Subagent additional_prompt with Custom LLM
- **Discovery:** When a subagent node uses Custom LLM, the node's `additional_prompt` IS included in the system message sent to Custom LLM (confirmed in last_system_prompt.txt). However, LangGraph ignores it because it uses its own intent classification and routing.
- **Takeaway:** ElevenLabs composes prompts correctly, but Custom LLM (LangGraph) needs to be aware of and respect the workflow context in the system prompt.

#### 4. Multi-turn auth collection in LangGraph (auth_collect node)
- **What we built:** A dedicated `auth_collect` node that reads conversation history to determine which auth field to ask for next (TC Kimlik last 4, DOB, father initial). Uses `is_auth_collecting()` to detect ongoing auth flow and skip LLM intent classification.
- **Result:** Field collection worked (1/3 → 2/3 → 3/3 → confirmation). But after user confirmed and webhook returned 200, the next turn either looped back to auth or classified as FAQ.
- **Root cause:** ElevenLabs is stateless — `citizen_profile` set in LangGraph state doesn't persist to the next turn. The workflow needs to transition to Authenticated Service node for state to change.

#### 5. Triggering workflow transition via notify_condition_1_met tool call
- **Discovery:** ElevenLabs injects `notify_condition_X_met` tools into Custom LLM requests. The system prompt says "call this tool when the condition is met." We returned this tool call in SSE response after successful auth.
- **Result:** ElevenLabs did NOT transition to the next workflow node. Instead, it sent a new request immediately (without user input), creating an infinite loop. The tool call was acknowledged but the workflow edge was not triggered.
- **Takeaway:** `notify_condition_X_met` tool calls from Custom LLM may not trigger workflow transitions the same way they do from native LLMs. This appears to be a platform limitation or requires a different SSE format than what we used.

#### 6. Sending tool call with content vs without content
- **Tried:** Sending both tool_call + content in same response, then only tool_call without content.
- **Result:** Neither triggered workflow transition. Without content, ElevenLabs entered infinite retry loop (re-sending the same request repeatedly).
- **Takeaway:** Custom LLM responses that contain only tool calls (no text content) cause ElevenLabs to retry, likely because TTS has nothing to speak.

### Key Platform Observations

1. **ElevenLabs sends full conversation history** with every Custom LLM request — this is the mechanism for "memory" in a stateless architecture.
2. **Workflow subagent additional_prompt** is appended to the system message sent to Custom LLM, appearing as "Specific goal for this portion of the conversation" in the prompt.
3. **notify_condition_X_met tools** are injected into every Custom LLM request when a workflow is active, but calling them from Custom LLM does not appear to trigger workflow transitions.
4. **System prompt length changes** (6630 vs 6434) suggest ElevenLabs occasionally sends slightly different prompts, possibly related to internal orchestrator state.
5. **deploy.py overwrites dashboard settings** — running `python -m agent.deploy` sets base agent LLM to GPT-4o (hardcoded in deploy script), overriding any Custom LLM configuration set in dashboard.

### Oscar's Auth Principle
> "Authentication cannot be left to conversational inference. Instead, it must be architected through isolated sub-agents, tool-based verification, and conditional workflow routing that ensures only authenticated users reach privileged operations."

Our webhook-based auth (200/401) is deterministic. The challenge is integrating this with ElevenLabs workflow transitions when using Custom LLM.

### Open Questions
- How to trigger workflow node transitions from Custom LLM? Is `notify_condition_X_met` the correct mechanism, and if so, what SSE format does it require?
- Can Custom LLM and workflow dispatch tool coexist? The dispatch tool works with native LLMs but we couldn't get it to fire when Custom LLM handles the conversation.
- Is there an alternative pattern for auth gating with Custom LLM that doesn't require workflow transitions? (e.g., using dynamic variables updated by webhook tool assignments)
