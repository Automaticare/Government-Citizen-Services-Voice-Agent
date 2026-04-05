***

title: System tools
subtitle: Update the internal state of conversations without external requests.
-------------------------------------------------------------------------------

**System tools** enable your assistant to update the internal state of a conversation. Unlike [server tools](/docs/eleven-agents/customization/tools/server-tools) or [client tools](/docs/eleven-agents/customization/tools/client-tools), system tools don't make external API calls or trigger client-side functions—they modify the internal state of the conversation without making external calls.

## Overview

Some applications require agents to control the flow or state of a conversation.
System tools provide this capability by allowing the assistant to perform actions related to the state of the call that don't require communicating with external servers or the client.

### Available system tools

<CardGroup cols={2}>
  <Card title="End call" icon="duotone square-phone-hangup" href="/docs/eleven-agents/customization/tools/system-tools/end-call">
    Let your agent automatically terminate a conversation when appropriate conditions are met.
  </Card>

  <Card title="Language detection" icon="duotone earth-europe" href="/docs/eleven-agents/customization/tools/system-tools/language-detection">
    Enable your agent to automatically switch to the user's language during conversations.
  </Card>

  <Card title="Agent transfer" icon="duotone arrow-right-arrow-left" href="/docs/eleven-agents/customization/tools/system-tools/agent-transfer">
    Seamlessly transfer conversations between AI agents based on defined conditions.
  </Card>

  <Card title="Transfer to number" icon="duotone user-headset" href="/docs/eleven-agents/customization/tools/system-tools/transfer-to-number">
    Transfer calls to external phone numbers or SIP URIs.
  </Card>

  <Card title="Skip turn" icon="duotone forward" href="/docs/eleven-agents/customization/tools/system-tools/skip-turn">
    Enable the agent to skip their turns if the LLM detects the agent should not speak yet.
  </Card>

  <Card title="Play keypad touch tone" icon="duotone phone-office" href="/docs/eleven-agents/customization/tools/system-tools/play-keypad-touch-tone">
    Enable agents to play DTMF tones to interact with automated phone systems and navigate menus.
  </Card>

  <Card title="Voicemail detection" icon="duotone voicemail" href="/docs/eleven-agents/customization/tools/system-tools/voicemail-detection">
    Enable agents to automatically detect voicemail systems and optionally leave messages.
  </Card>
</CardGroup>

## Implementation

When creating an agent via API, you can add system tools to your agent configuration. Here's how to implement both the end call and language detection tools:

## Custom LLM integration

When using a custom LLM with ElevenLabs agents, system tools are exposed as function definitions that your LLM can call. Each system tool has specific parameters and trigger conditions:

### Available system tools

<AccordionGroup>
  <Accordion title="End call">
    **Purpose**: Automatically terminate conversations when appropriate conditions are met.

    **Trigger conditions**: The LLM should call this tool when:

    * The main task has been completed and user is satisfied
    * The conversation reached natural conclusion with mutual agreement
    * The user explicitly indicates they want to end the conversation

    **Parameters**:

    * `reason` (string, required): The reason for ending the call
    * `message` (string, optional): A farewell message to send to the user before ending the call

    **Function call format**:

    ```json
    {
      "type": "function",
      "function": {
        "name": "end_call",
        "arguments": "{\"reason\": \"Task completed successfully\", \"message\": \"Thank you for using our service. Have a great day!\"}"
      }
    }
    ```

    **Implementation**: Configure as a system tool in your agent settings. The LLM will receive detailed instructions about when to call this function.

    Learn more: [End call tool](/docs/eleven-agents/customization/tools/system-tools/end-call)
  </Accordion>

  <Accordion title="Language detection">
    **Purpose**: Automatically switch to the user's detected language during conversations.

    **Trigger conditions**: The LLM should call this tool when:

    * User speaks in a different language than the current conversation language
    * User explicitly requests to switch languages
    * Multi-language support is needed for the conversation

    **Parameters**:

    * `reason` (string, required): The reason for the language switch
    * `language` (string, required): The language code to switch to (must be in supported languages list)

    **Function call format**:

    ```json
    {
      "type": "function",
      "function": {
        "name": "language_detection",
        "arguments": "{\"reason\": \"User requested Spanish\", \"language\": \"es\"}"
      }
    }
    ```

    **Implementation**: Configure supported languages in agent settings and add the language detection system tool. The agent will automatically switch voice and responses to match detected languages.

    Learn more: [Language detection tool](/docs/eleven-agents/customization/tools/system-tools/language-detection)
  </Accordion>

  <Accordion title="Agent transfer">
    **Purpose**: Transfer conversations between specialized AI agents based on user needs.

    **Trigger conditions**: The LLM should call this tool when:

    * User request requires specialized knowledge or different agent capabilities
    * Current agent cannot adequately handle the query
    * Conversation flow indicates need for different agent type

    **Parameters**:

    * `reason` (string, optional): The reason for the agent transfer
    * `agent_number` (integer, required): Zero-indexed number of the agent to transfer to (based on configured transfer rules)

    **Function call format**:

    ```json
    {
      "type": "function",
      "function": {
        "name": "transfer_to_agent",
        "arguments": "{\"reason\": \"User needs billing support\", \"agent_number\": 0}"
      }
    }
    ```

    **Implementation**: Define transfer rules mapping conditions to specific agent IDs. Configure which agents the current agent can transfer to. Agents are referenced by zero-indexed numbers in the transfer configuration.

    Learn more: [Agent transfer tool](/docs/eleven-agents/customization/tools/system-tools/agent-transfer)
  </Accordion>

  <Accordion title="Transfer to number">
    **Purpose**: Seamlessly hand off conversations to human operators when AI assistance is insufficient.

    **Trigger conditions**: The LLM should call this tool when:

    * Complex issues requiring human judgment
    * User explicitly requests human assistance
    * AI reaches limits of capability for the specific request
    * Escalation protocols are triggered

    **Parameters**:

    * `reason` (string, optional): The reason for the transfer
    * `transfer_number` (string, required): The phone number to transfer to (must match configured numbers)
    * `client_message` (string, required): Message read to the client while waiting for transfer
    * `agent_message` (string, required): Message for the human operator receiving the call

    **Function call format**:

    ```json
    {
      "type": "function",
      "function": {
        "name": "transfer_to_number",
        "arguments": "{\"reason\": \"Complex billing issue\", \"transfer_number\": \"+15551234567\", \"client_message\": \"I'm transferring you to a billing specialist who can help with your account.\", \"agent_message\": \"Customer has a complex billing dispute about order #12345 from last month.\"}"
      }
    }
    ```

    **Implementation**: Configure transfer phone numbers and conditions. Define messages for both customer and receiving human operator. Works with both Twilio and SIP trunking.

    Learn more: [Transfer to number tool](/docs/eleven-agents/customization/tools/system-tools/transfer-to-number)
  </Accordion>

  <Accordion title="Skip turn">
    **Purpose**: Allow the agent to pause and wait for user input without speaking.

    **Trigger conditions**: The LLM should call this tool when:

    * User indicates they need a moment ("Give me a second", "Let me think")
    * User requests pause in conversation flow
    * Agent detects user needs time to process information

    **Parameters**:

    * `reason` (string, optional): Free-form reason explaining why the pause is needed

    **Function call format**:

    ```json
    {
      "type": "function",
      "function": {
        "name": "skip_turn",
        "arguments": "{\"reason\": \"User requested time to think\"}"
      }
    }
    ```

    **Implementation**: No additional configuration needed. The tool simply signals the agent to remain silent until the user speaks again.

    Learn more: [Skip turn tool](/docs/eleven-agents/customization/tools/system-tools/skip-turn)
  </Accordion>

  <Accordion title="Play keypad touch tone">
    **Parameters**:

    * `reason` (string, optional): The reason for playing the DTMF tones (e.g., "navigating to extension", "entering PIN")
    * `dtmf_tones` (string, required): The DTMF sequence to play. Valid characters: 0-9, \*, #, w (0.5s pause), W (1s pause)

    **Function call format**:

    ```json
    {
      "type": "function",
      "function": {
        "name": "play_keypad_touch_tone",
        "arguments": "{"reason": "Navigating to customer service", "dtmf_tones": "2"}"
      }
    }
    ```

    Learn more: [Play keypad touch tone tool](/docs/eleven-agents/customization/tools/system-tools/play-keypad-touch-tone)
  </Accordion>

  <Accordion title="Voicemail detection">
    **Parameters**:

    * `reason` (string, required): The reason for detecting voicemail (e.g., "automated greeting detected", "no human response")

    **Function call format**:

    ```json
    {
      "type": "function",
      "function": {
        "name": "voicemail_detection",
        "arguments": "{\"reason\": \"Automated greeting detected with request to leave message\"}"
      }
    }
    ```

    Learn more: [Voicemail detection tool](/docs/eleven-agents/customization/tools/system-tools/voicemail-detection)
  </Accordion>
</AccordionGroup>

<CodeGroup>
  ```python
  from elevenlabs import (
      ConversationalConfig,
      ElevenLabs,
      AgentConfig,
      PromptAgent,
      PromptAgentInputToolsItem_System,
  )

  # Initialize the client
  elevenlabs = ElevenLabs(api_key="YOUR_API_KEY")

  # Create system tools
  end_call_tool = PromptAgentInputToolsItem_System(
      name="end_call",
      description=""  # Optional: Customize when the tool should be triggered
  )

  language_detection_tool = PromptAgentInputToolsItem_System(
      name="language_detection",
      description=""  # Optional: Customize when the tool should be triggered
  )

  # Create the agent configuration with both tools
  conversation_config = ConversationalConfig(
      agent=AgentConfig(
          prompt=PromptAgent(
              tools=[end_call_tool, language_detection_tool]
          )
      )
  )

  # Create the agent
  response = elevenlabs.conversational_ai.agents.create(
      conversation_config=conversation_config
  )
  ```

  ```javascript
  import { ElevenLabs } from '@elevenlabs/elevenlabs-js';

  // Initialize the client
  const elevenlabs = new ElevenLabs({
    apiKey: 'YOUR_API_KEY',
  });

  // Create the agent with system tools
  await elevenlabs.conversationalAi.agents.create({
    conversationConfig: {
      agent: {
        prompt: {
          tools: [
            {
              type: 'system',
              name: 'end_call',
              description: '',
            },
            {
              type: 'system',
              name: 'language_detection',
              description: '',
            },
          ],
        },
      },
    },
  });
  ```
</CodeGroup>

## FAQ

<AccordionGroup>
  <Accordion title="Can system tools be combined with other tool types?">
    Yes, system tools can be used alongside server tools and client tools in the same assistant.
    This allows for comprehensive functionality that combines internal state management with
    external interactions.
  </Accordion>
</AccordionGroup>

```
```
