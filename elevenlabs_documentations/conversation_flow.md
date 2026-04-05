***

title: Conversation flow
subtitle: >-
Configure how your assistant handles timeouts, interruptions, and turn-taking
during conversations.
---------------------

## Overview

Conversation flow settings determine how your assistant handles periods of user silence, interruptions during speech, and turn-taking behavior. These settings help create more natural conversations and can be customized based on your use case.

<CardGroup cols={2}>
  <Card title="Turn timeout" icon="clock" href="#turn-timeout">
    Configure how long your assistant waits during periods of silence
  </Card>

  <Card title="Soft timeout" icon="hourglass-half" href="#soft-timeout">
    Provide natural audio feedback when your agent needs time to think
  </Card>

  <Card title="Interruptions" icon="hand" href="#interruptions">
    Control whether users can interrupt your assistant while speaking
  </Card>

  <Card title="Turn eagerness" icon="arrows-turn-to-dots" href="#turn-eagerness">
    Adjust how quickly your assistant responds to user input
  </Card>
</CardGroup>

## Turn timeout

Turn timeout determines how long your assistant waits during periods of user silence before prompting for a response.

### Configuration

Turn timeout settings can be configured in the agent's **Advanced** tab under **Turn Timeout**.

The timeout duration is specified in seconds and determines how long the assistant will wait in silence before prompting the user. Turn timeouts must be between 1 and 30 seconds.

<Frame background="subtle">
  ![Timeout settings](file:cbe7b21f-113e-44e1-9b5c-ddd3e36d455d)
</Frame>

<Note>
  Choose an appropriate timeout duration based on your use case. Shorter timeouts create more
  responsive conversations but may interrupt users who need more time to respond, leading to a less
  natural conversation.
</Note>

### Best practices

* Set shorter timeouts (5-10 seconds) for casual conversations where quick back-and-forth is expected
* Use longer timeouts (10-30 seconds) when users may need more time to think or formulate complex responses
* Consider your user context - customer service may benefit from shorter timeouts while technical support may need longer ones

## Soft timeout

Soft timeout provides immediate audio feedback when the LLM takes longer than expected to generate a response. Instead of awkward silence while waiting, your agent speaks a brief filler phrase like "Hmm..." or "Let me think..." to maintain natural conversational flow.

This feature is useful for:

* Complex queries requiring longer LLM processing
* Handling variable latency from LLM providers
* Creating more human-like conversations with natural thinking pauses

### How it works

1. When the user finishes speaking, the system starts generating an LLM response
2. A timer begins based on the configured timeout duration
3. If the LLM response arrives **before** the timeout, no filler is spoken
4. If the timeout is reached **before** the LLM responds:
   * The configured filler message is spoken immediately
   * The agent continues waiting for the actual response
   * Once ready, the agent speaks the full LLM response

Soft timeout triggers only once per turn to prevent multiple fillers in succession.

### Configuration

Soft timeout settings are available in the agent's **Advanced** tab under **Soft timeout**.

<Frame background="subtle">
  ![Soft timeout settings](file:caca8ab8-e15c-4a4f-b5b1-df69958c010d)
</Frame>

#### Timeout duration

The time in seconds before the filler message is spoken while waiting for the LLM response.

| Setting         | Description            |
| --------------- | ---------------------- |
| **Default**     | `-1` (disabled)        |
| **Range**       | `0.5` to `8.0` seconds |
| **Recommended** | `3.0` seconds          |

<Tip>
  Start with 3.0 seconds—long enough to avoid unnecessary fillers on fast responses, short enough to
  prevent awkward silences.
</Tip>

#### Static message

A predefined filler phrase spoken when soft timeout triggers.

| Setting     | Description        |
| ----------- | ------------------ |
| **Default** | `"Hhmmmm...yeah."` |
| **Length**  | 1–200 characters   |

This message supports:

* **Language overrides**: Auto-translates to additional languages configured for your agent
* **Client overrides**: Can be customized per-call via the SDK

#### LLM-generated message

When enabled, generates a contextually-appropriate filler phrase dynamically using a lightweight LLM, instead of the static message.

| Setting      | Description                             |
| ------------ | --------------------------------------- |
| **Default**  | `false`                                 |
| **Fallback** | Uses static message if generation fails |

The system uses recent conversation context (up to 4 messages, 1000 characters) to generate relevant fillers like "Hmm...", "I see...", "Understood...", "Got it...", or "Alright..."

<Note>
  A static fallback message is still required when using LLM-generated messages.
</Note>

### Best practices

* Avoid time indicators in filler messages (e.g., "One second...") as actual response times are unpredictable
* Disable soft timeout for quick FAQ bots where responses are consistently fast

## Interruptions

Interruption handling determines whether users can interrupt your assistant while it's speaking.

### Configuration

Interruption settings can be configured in the agent's **Advanced** tab under **Client Events**.

To enable interruptions, make sure interruption is a selected client event.

#### Interruptions enabled

<Frame background="subtle">
  ![Interruption allowed](file:05cfd890-916a-4810-9cdf-7cba66abbe17)
</Frame>

#### Interruptions disabled

<Frame background="subtle">
  ![Interruption ignored](file:f285a445-0b3f-4d4e-aff1-9257a1bd7879)
</Frame>

<Note>
  Disable interruptions when the complete delivery of information is crucial, such as legal
  disclaimers or safety instructions.
</Note>

### Best practices for interruptions

* Enable interruptions for natural conversational flows where back-and-forth dialogue is expected
* Disable interruptions when message completion is critical (e.g., terms and conditions, safety information)
* Consider your use case context - customer service may benefit from interruptions while information delivery may not

## Turn eagerness

Turn eagerness controls how quickly your assistant responds to user input during conversation. This setting determines how eager the assistant is to take turns and start speaking based on detected speech patterns.

### How it works

The assistant now includes two key improvements for more natural turn-taking:

1. **Faster response generation** - The assistant starts speaking after receiving enough words and a comma from the language model, rather than waiting for complete sentences. This reduces latency and creates more responsive conversations, especially when the assistant has longer responses.

2. **Configurable turn eagerness** - Control how quickly the assistant interprets pauses or speech patterns as opportunities to respond.

### Configuration

Turn eagerness can be configured in the dashboard Agent settings or via the [API](/docs/api-reference/agents/create#request.body.conversation_config.turn.turn_eagerness). Three modes are available:

* **Eager** - The assistant responds quickly to user input, jumping in at the earliest opportunity. Best for fast-paced conversations where immediate responses are valued.
* **Normal** - Balanced turn-taking that works well for most conversational scenarios. The assistant waits for natural conversation breaks before responding.
* **Patient** - The assistant waits longer before taking its turn, giving users more time to complete their thoughts. Ideal for collecting detailed information or when users need time to formulate responses.

<Note>
  Turn eagerness is especially powerful when combined with workflows. You can dynamically adjust the
  assistant's responsiveness based on context—making it jump in faster during casual conversation,
  or wait longer when collecting sensitive information like phone numbers or email addresses.
</Note>

### Best practices for turn eagerness

* Use **Eager** mode for customer service scenarios where quick responses improve user experience
* Use **Patient** mode when collecting structured information like phone numbers, addresses, or email addresses
* Use **Normal** mode as a default for general conversational flows
* Combine with workflows to dynamically adjust turn eagerness based on conversation context
* Test different settings with your specific use case to find the optimal balance

## Recommended configurations

<AccordionGroup>
  <Accordion title="Customer service">
    * Shorter timeouts (5-10 seconds) for responsive interactions - Enable interruptions to allow
      customers to interject with questions - **Eager** turn eagerness for quick, responsive
      conversations
  </Accordion>

  <Accordion title="Information collection">
    * Moderate timeouts (10-15 seconds) to allow users time to gather information - Enable
      interruptions for natural conversation flow - **Patient** turn eagerness when collecting phone
      numbers, addresses, or email addresses
  </Accordion>

  <Accordion title="Legal disclaimers">
    * Longer timeouts (15-30 seconds) to allow for complex responses - Disable interruptions to
      ensure full delivery of legal information - **Normal** turn eagerness to maintain steady pacing
  </Accordion>

  <Accordion title="Conversational EdTech">
    * Longer timeouts (10-30 seconds) to allow time to think and formulate responses - Enable
      interruptions to allow students to interject with questions - **Patient** turn eagerness to give
      students adequate time to respond
  </Accordion>
</AccordionGroup>
