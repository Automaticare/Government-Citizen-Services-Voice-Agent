***

title: Workflows
subtitle: Build sophisticated conversation flows with visual graph-based workflows
----------------------------------------------------------------------------------

<Frame background="subtle">
  <iframe width="100%" height="400" src="https://www.youtube.com/embed/7gtzXAaA82I" title="Agent Workflows Walkthrough" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen />
</Frame>

## Overview

Agent Workflows provide a powerful visual interface for designing complex conversation flows in ElevenAgents. Instead of relying on linear conversation paths, workflows enable you to create sophisticated, branching conversation graphs that adapt dynamically to user needs.

<Frame background="subtle">
  ![Workflow Overview](file:8f6da5cc-709b-411d-9f65-52f13e109800)
</Frame>

## Node types

Workflows are composed of different node types, each serving a specific purpose in your conversation flow.

<Frame background="subtle">
  ![Node Types](file:4011d188-41d9-49f3-a55e-e3b73c8e5716)
</Frame>

### Subagent nodes

Subagent nodes allow you to modify agent behavior at specific points in your workflow. These modifications are applied on top of the base agent configuration, or can override the current agent's config completely, giving you fine-grained control over each conversation phase.
Any of an agent's configuration, tools available, and attached knowledge base items can be updated/overwitten.

<Tabs>
  <Tab title="General">
    <Frame background="subtle">
      <img src="file:01a96f80-9afb-4fec-95ab-ca0c328197cd" alt="Subagent Extra Agent Config" />
    </Frame>

    Modify core agent settings for this specific node:

    * **System Prompt**: Append or override system instructions to guide agent behavior
    * **LLM Selection**: Choose a different language model (e.g., switch from Gemini 2.0 Flash to a more powerful model for complex reasoning tasks)
    * **Voice Configuration**: Change voice settings including speed, tone, or even switch to a different voice

    **Use Cases:**

    * Use a more powerful LLM for complex decision-making nodes
    * Apply stricter conversation guidelines during sensitive information gathering
    * Change voice characteristics for different conversation phases
    * Modify agent personality for specific interaction types
  </Tab>

  <Tab title="Knowledge Base">
    <Frame background="subtle">
      <img src="file:e2cccefe-1b7a-40fa-b149-00fce58aeda4" alt="Subagent Extra Knowledge Base" />
    </Frame>

    Add node-specific knowledge without affecting the global knowledge base:

    * **Include Global Knowledge Base**: Toggle whether to include the agent's main knowledge base
    * **Additional Documents**: Add documents specific to this conversation phase
    * **Dynamic Knowledge**: Inject contextual information based on workflow state

    **Use Cases:**

    * Add product-specific documentation during sales conversations
    * Include compliance guidelines during authentication
    * Provide troubleshooting guides for support flows
    * Add pricing information only after qualification
  </Tab>

  <Tab title="Tools">
    <Frame background="subtle">
      <img src="file:c2a33a63-8713-464e-b8e7-b88944dea9fd" alt="Subagent Extra Tools" />
    </Frame>

    Manage which tools are available to the agent at this node:

    * **Include Global Tools**: Toggle whether to include tools from the main agent configuration
    * **Additional Tools**: Add tools specific to this workflow node (e.g., webhook tools like `book_meeting`)
    * **Tool Type**: Specify whether tools are webhooks, API calls, or other integrations

    **Use Cases:**

    * Add authentication tools only after initial qualification
    * Enable payment processing tools at checkout nodes
    * Provide CRM access after user verification
    * Add scheduling tools for appointment booking phases
    * Include webhook tools for specific actions like booking meetings
  </Tab>
</Tabs>

### Dispatch tool node

Tool nodes execute a specific tool call during conversation flow. Unlike tools within subagents, tool nodes are dedicated execution points that guarantee the tool is called.

<Frame background="subtle">
  ![Tool Node Result Edges](file:31b1543e-64eb-43a4-9a4c-9b9ae4c150cb)
</Frame>

**Special Edge Configuration:**
Tool nodes have a unique edge type that allows routing to a new node based on the tool execution result. You can define:

* **Success path**: Where to route when the tool executes successfully
* **Failure path**: Where to route when the tool fails or returns an error

In future, futher branching conditions will be provided.

### Agent transfer node

Agent transfer node facilitate handoffs the conversation between different conversational agents, learn more [here](/docs/eleven-agents/customization/tools/system-tools/agent-transfer).

### Transfer to number node

Transfer to number nodes transitions from a conversation with an AI agent to a human agent via phone systems, learn more [here](/docs/eleven-agents/customization/tools/system-tools/transfer-to-number)

### End node

End call nodes terminate the conversation flow gracefully, learn more [here](/docs/eleven-agents/customization/tools/system-tools/transfer-to-number#:~:text=System%20tools-,End%20call,-Language%20detection)

## Edges and flow control

Edges define how conversations flow between nodes in your workflow. They support sophisticated routing logic that enables dynamic, context-aware conversation paths.

<Frame background="subtle">
  ![Workflow Edges](file:f51dfa4b-0fd2-4494-a4e9-16c30828efc0)
</Frame>

<Tabs>
  <Tab title="Forward Edges">
    Forward edges move the conversation to subsequent nodes in the workflow. They represent the primary flow of your conversation.

    <Frame background="subtle">
      ![Forward Edge Configuration](file:861ef620-f3c0-4f47-a123-8a9a839f7bf1)
    </Frame>
  </Tab>

  <Tab title="Backward Edges">
    Backward edges allow conversations to loop back to previous nodes, enabling iterative interactions and retry logic.

    <Frame background="subtle">
      ![Backward Edge Configuration](file:81fb55c4-056e-4472-878b-ab7dd72f181e)
    </Frame>

    **Use Cases:**

    * Retry failed authentication attempts
    * Loop back for additional information gathering
    * Re-qualification after changes in user requirements
    * Iterative troubleshooting processes
  </Tab>
</Tabs>

<Tabs>
  <Tab title="LLM Condition">
    Use LLM conditions to create dynamic conversation flows based on natural language evaluation. The LLM evaluates conditions in real-time to determine the appropriate path.

    <Frame background="subtle">
      ![LLM Condition Agent Transfer](file:50e5ed65-9b51-4f62-aab6-0b3385c68e67)
    </Frame>

    **Configuration Options:**

    * **Label**: Human-readable description of the edge condition (not processed by LLM)
    * **LLM Condition**: Natural language condition evaluated by the LLM
  </Tab>

  <Tab title="Expression">
    Use expressions to create conditional logic based on variables and structured data.

    <Frame background="subtle">
      ![Expression Agent Transfer](file:16b72928-7d2a-4fbd-bc32-a097eca95962)
    </Frame>

    **Configuration Options:**

    * **Label**: Human-readable description of the edge condition (not processed by LLM)
    * **Expression**: Deterministic evaluation criteria based on data structure
  </Tab>

  <Tab title="None">
    Unconditional transitions automatically move the conversation to the next node without any conditions.

    <Frame background="subtle">
      ![Unconditional Agent Transfer](file:10f3d6b1-c663-4046-a252-81b7aba64b2f)
    </Frame>

    **Use Cases:**

    * Sequential steps that always follow one another
    * Automatic progression after completing an action
    * Default fallback paths
  </Tab>
</Tabs>
