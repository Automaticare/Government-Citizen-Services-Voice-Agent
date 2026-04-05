***

title: End call
subtitle: Let your agent automatically hang up on the user.
-----------------------------------------------------------

<Warning>
  The **End Call** tool is added to agents created in the ElevenLabs dashboard by default. For
  agents created via API or SDK, if you would like to enable the End Call tool, you must add it
  manually as a system tool in your agent configuration. [See API Implementation
  below](#api-implementation) for details.
</Warning>

<Frame background="subtle">
  ![End call](file:6c2cb3d8-8dab-445d-843a-c18601a0c2ae)
</Frame>

## Overview

The **End Call** tool allows your conversational agent to terminate a call with the user. This is a system tool that provides flexibility in how and when calls are ended.

## Functionality

* **Default behavior**: The tool can operate without any user-defined prompts, ending the call when the conversation naturally concludes.
* **Custom prompts**: Users can specify conditions under which the call should end. For example:
  * End the call if the user says "goodbye."
  * Conclude the call when a specific task is completed.

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

### API Implementation

When creating an agent via API, you can add the End Call tool to your agent configuration. It should be defined as a system tool:

<CodeBlocks>
  ```python
  from elevenlabs import (
      ConversationalConfig,
      ElevenLabs,
      AgentConfig,
      PromptAgent,
      PromptAgentInputToolsItem_System
  )

  # Initialize the client
  elevenlabs = ElevenLabs(api_key="YOUR_API_KEY")

  # Create the end call tool
  end_call_tool = PromptAgentInputToolsItem_System(
      name="end_call",
      description=""  # Optional: Customize when the tool should be triggered
  )

  # Create the agent configuration
  conversation_config = ConversationalConfig(
      agent=AgentConfig(
          prompt=PromptAgent(
              tools=[end_call_tool]
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

  // Create the agent with end call tool
  await elevenlabs.conversationalAi.agents.create({
    conversationConfig: {
      agent: {
        prompt: {
          tools: [
            {
              type: 'system',
              name: 'end_call',
              description: '', // Optional: Customize when the tool should be triggered
            },
          ],
        },
      },
    },
  });
  ```

  ```bash
  curl -X POST https://api.elevenlabs.io/v1/convai/agents/create \
       -H "xi-api-key: YOUR_API_KEY" \
       -H "Content-Type: application/json" \
       -d '{
    "conversation_config": {
      "agent": {
        "prompt": {
          "tools": [
            {
              "type": "system",
              "name": "end_call",
              "description": ""
            }
          ]
        }
      }
    }
  }'
  ```
</CodeBlocks>

<Tip>
  Leave the description blank to use the default end call prompt.
</Tip>

## Example prompts

**Example 1: Basic End Call**

```
End the call when the user says goodbye, thank you, or indicates they have no more questions.
```

**Example 2: End Call with Custom Prompt**

```
End the call when the user says goodbye, thank you, or indicates they have no more questions. You can only end the call after all their questions have been answered. Please end the call only after confirming that the user doesn't need any additional assistance.
```
