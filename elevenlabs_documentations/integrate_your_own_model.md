***

title: Integrate your own model
subtitle: Connect an agent to your own LLM or host your own server.
-------------------------------------------------------------------

<Note>
  Custom LLM allows you to connect your conversations to your own LLM via an external endpoint.
  ElevenLabs also supports [natively integrated LLMs](/docs/eleven-agents/customization/llm)
</Note>

**Custom LLMs** let you bring your own OpenAI API key or run an entirely custom LLM server.

## Overview

By default, we use our own internal credentials for popular models like OpenAI. To use a custom LLM server, it must align with one of the following OpenAI-compatible request/response structures:

* [Chat Completions API](https://platform.openai.com/docs/api-reference/chat/create) (`/v1/chat/completions`)
* [Responses API](https://platform.openai.com/docs/api-reference/responses/create) (`/v1/responses`)

<Info>
  The Responses API is OpenAI's newer API format that supports additional features. Both API formats
  are fully supported for custom LLM integration.
</Info>

The following guides cover both use cases:

1. **Bring your own OpenAI key**: Use your own OpenAI API key with our platform.
2. **Custom LLM server**: Host and connect your own LLM server implementation.

You'll learn how to:

* Store your OpenAI API key in ElevenLabs
* Host a server that replicates OpenAI's [Chat Completions](https://platform.openai.com/docs/api-reference/chat/create) or [Responses](https://platform.openai.com/docs/api-reference/responses/create) endpoint
* Direct ElevenLabs to your custom endpoint
* Pass extra parameters to your LLM as needed

## Using your own OpenAI key

To integrate a custom OpenAI key, update your agent settings in the ElevenLabs dashboard to point to your custom LLM server and create a secret containing your `OPENAI_API_KEY`:

<Steps>
  <Step>
    In your Agent settings in the ElevenLabs dashboard, select "Custom LLM" from the "LLM" dropdown menu on the right.

    <Frame background="subtle">
      ![Add Secret](file:6a816317-86fb-4f60-804f-62ae9d219589)
    </Frame>
  </Step>

  <Step>
    Click on the field under "LLM" and scroll down to select "Custom LLM".
  </Step>

  <Step>
    Enter the server URL and the Model ID of your custom LLM server.

    <Frame background="subtle">
      ![Enter url](file:e16652a0-510b-4afa-9f92-b3439e0b20e9)
    </Frame>
  </Step>

  <Step>
    Click the dropdown under "API key" and select "Create new secret". Name the key `OPENAI_API_KEY` and add the key to the "value" field and click "Add secret".
  </Step>

  <Step>
    Click the "x" button to close the LLM modal and click "Publish" to save your changes.
  </Step>
</Steps>

## Custom LLM Server

To bring a custom LLM server, set up a compatible server endpoint using OpenAI's style. You can implement either the Chat Completions API (`/v1/chat/completions`) or the Responses API (`/v1/responses`).

Both endpoints must return responses in SSE (Server-Sent Events) format with `Content-Type: text/event-stream`.

<Tabs>
  <Tab title="Chat Completions API">
    The Chat Completions API uses the `/v1/chat/completions` endpoint.

    Each chunk must be formatted as `data: {json}\n\n` and the stream must end with `data: [DONE]\n\n`.

    Here's an example server implementation:

    ```python
    import json
    import os
    import fastapi
    from fastapi.responses import StreamingResponse
    from openai import AsyncOpenAI
    import uvicorn
    import logging
    from dotenv import load_dotenv
    from pydantic import BaseModel
    from typing import List, Optional

    # Load environment variables from .env file
    load_dotenv()

    # Retrieve API key from environment
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not found in environment variables")

    app = fastapi.FastAPI()
    oai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    class Message(BaseModel):
        role: str
        content: str

    class ChatCompletionRequest(BaseModel):
        messages: List[Message]
        model: str
        temperature: Optional[float] = 0.7
        max_tokens: Optional[int] = None
        stream: Optional[bool] = False
        user_id: Optional[str] = None

    @app.post("/v1/chat/completions")
    async def create_chat_completion(request: ChatCompletionRequest) -> StreamingResponse:
        oai_request = request.dict(exclude_none=True)
        if "user_id" in oai_request:
            oai_request["user"] = oai_request.pop("user_id")

        chat_completion_coroutine = await oai_client.chat.completions.create(**oai_request)

        async def event_stream():
            try:
                async for chunk in chat_completion_coroutine:
                    # Convert the ChatCompletionChunk to a dictionary before JSON serialization
                    chunk_dict = chunk.model_dump()
                    yield f"data: {json.dumps(chunk_dict)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logging.error("An error occurred: %s", str(e))
                yield f"data: {json.dumps({'error': 'Internal error occurred!'})}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8013)
    ```
  </Tab>

  <Tab title="Responses API">
    The Responses API uses the `/v1/responses` endpoint.

    Each chunk must be formatted as `event: {type}\ndata: {json}\n\n` and the stream must end with `data: [DONE]\n\n`. The minimum required events are:

    * `response.output_text.delta` - for streaming text content
    * `response.completed` - to signal completion

    <CodeBlocks>
      ```python title="server.py"
      import json
      import os
      import fastapi
      from fastapi.responses import StreamingResponse
      from openai import AsyncOpenAI
      import uvicorn
      import logging
      from dotenv import load_dotenv
      from pydantic import BaseModel
      from typing import List, Optional

      load_dotenv()

      OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
      if not OPENAI_API_KEY:
          raise ValueError("OPENAI_API_KEY not found in environment variables")

      app = fastapi.FastAPI()
      oai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

      class InputMessage(BaseModel):
          role: str
          content: str

      class ResponseCreateRequest(BaseModel):
          model: str
          input: List[InputMessage]
          instructions: Optional[str] = None
          temperature: Optional[float] = 0.7
          max_output_tokens: Optional[int] = None
          stream: Optional[bool] = False

      @app.post("/v1/responses")
      async def create_response(request: ResponseCreateRequest) -> StreamingResponse:
          input_messages = [{"role": msg.role, "content": msg.content} for msg in request.input]

          response_stream = await oai_client.responses.create(
              model=request.model,
              input=input_messages,
              instructions=request.instructions,
              temperature=request.temperature,
              max_output_tokens=request.max_output_tokens,
              stream=True
          )

          async def event_stream():
              try:
                  async for event in response_stream:
                      if event.type == "response.output_text.delta":
                          yield f"event: response.output_text.delta\ndata: {json.dumps({'type': 'response.output_text.delta', 'delta': event.delta})}\n\n"
                      elif event.type == "response.completed":
                          yield f"event: response.completed\ndata: {json.dumps({'type': 'response.completed', 'response': {'id': event.response.id, 'status': 'completed'}})}\n\n"

                  yield "data: [DONE]\n\n"

              except Exception as e:
                  logging.error("An error occurred: %s", str(e))
                  yield f"event: error\ndata: {json.dumps({'type': 'error', 'error': {'message': str(e)}})}\n\n"

          return StreamingResponse(event_stream(), media_type="text/event-stream")

      if __name__ == "__main__":
          uvicorn.run(app, host="0.0.0.0", port=8013)

      ```

      ```typescript title="server.ts"
      import express, { Request, Response } from 'express';
      import OpenAI from 'openai';

      const app = express();
      app.use(express.json());

      const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

      interface InputMessage {
        role: string;
        content: string;
      }

      interface ResponseCreateRequest {
        model: string;
        input: InputMessage[];
        instructions?: string;
        temperature?: number;
        max_output_tokens?: number;
        stream?: boolean;
      }

      app.post('/v1/responses', async (req: Request, res: Response) => {
        const request = req.body as ResponseCreateRequest;

        res.setHeader('Content-Type', 'text/event-stream');
        res.setHeader('Cache-Control', 'no-cache');
        res.setHeader('Connection', 'keep-alive');

        try {
          const stream = await openai.responses.create({
            model: request.model,
            input: request.input,
            instructions: request.instructions,
            temperature: request.temperature ?? 0.7,
            max_output_tokens: request.max_output_tokens,
            stream: true,
          });

          for await (const event of stream) {
            if (event.type === 'response.output_text.delta') {
              res.write(
                `event: response.output_text.delta\ndata: ${JSON.stringify({ type: 'response.output_text.delta', delta: event.delta })}\n\n`
              );
            } else if (event.type === 'response.completed') {
              res.write(
                `event: response.completed\ndata: ${JSON.stringify({ type: 'response.completed', response: { id: event.response.id, status: 'completed' } })}\n\n`
              );
            }
          }

          res.write('data: [DONE]\n\n');
          res.end();
        } catch (error) {
          console.error('An error occurred:', error);
          res.write(
            `event: error\ndata: ${JSON.stringify({ type: 'error', error: { message: String(error) } })}\n\n`
          );
          res.end();
        }
      });

      app.listen(8013, () => console.log('Server running on port 8013'));
      ```
    </CodeBlocks>
  </Tab>
</Tabs>

Run this code or your own server code.

<Frame background="subtle">
  ![](file:a8cb2253-0fe1-4987-902a-07ad9c1e0d04)
</Frame>

### Setting Up a Public URL for Your Server

To make your server accessible, create a public URL using a tunneling tool like ngrok:

```shell
ngrok http --url=<Your url>.ngrok.app 8013
```

<Frame background="subtle">
  ![](file:35c3ef98-455e-4afa-92d4-a3e68763e746)
</Frame>

### Configuring ElevenLabs CustomLLM

Next, update your agent settings in the ElevenLabs dashboard to point to your custom LLM server.

<Frame background="subtle">
  ![](file:a27753c4-693c-4d76-a486-02e0ed5fd7f1)
</Frame>

Direct your server URL to ngrok endpoint and set "Limit token usage" to 5000.

You can now start interacting with your agent with your own LLM server.

## Optimizing for slow processing LLMs

If your custom LLM has slow processing times (perhaps due to agentic reasoning or pre-processing requirements) you can improve the conversational flow by implementing **buffer words** in your streaming responses. This technique helps maintain natural speech prosody while your LLM generates the complete response.

### Buffer words

When your LLM needs more time to process the full response, return an initial response ending with `"... "` (ellipsis followed by a space). This allows the Text to Speech system to maintain natural flow while keeping the conversation feeling dynamic.
This creates natural pauses that flow well into subsequent content that the LLM can reason longer about. The extra space is crucial to ensure that the subsequent content is not appended to the "..." which can lead to audio distortions.

### Implementation

Here's how to modify your custom LLM server to implement buffer words:

<CodeBlocks>
  ```python title="server.py"
  @app.post("/v1/chat/completions")
  async def create_chat_completion(request: ChatCompletionRequest) -> StreamingResponse:
      oai_request = request.dict(exclude_none=True)
      if "user_id" in oai_request:
          oai_request["user"] = oai_request.pop("user_id")

      async def event_stream():
          try:
              # Send initial buffer chunk while processing
              initial_chunk = {
                  "id": "chatcmpl-buffer",
                  "object": "chat.completion.chunk",
                  "created": 1234567890,
                  "model": request.model,
                  "choices": [{
                      "delta": {"content": "Let me think about that... "},
                      "index": 0,
                      "finish_reason": None
                  }]
              }
              yield f"data: {json.dumps(initial_chunk)}\n\n"

              # Process the actual LLM response
              chat_completion_coroutine = await oai_client.chat.completions.create(**oai_request)

              async for chunk in chat_completion_coroutine:
                  chunk_dict = chunk.model_dump()
                  yield f"data: {json.dumps(chunk_dict)}\n\n"
              yield "data: [DONE]\n\n"

          except Exception as e:
              logging.error("An error occurred: %s", str(e))
              yield f"data: {json.dumps({'error': 'Internal error occurred!'})}\n\n"

      return StreamingResponse(event_stream(), media_type="text/event-stream")

  ```

  ```typescript title="server.ts"
  app.post('/v1/chat/completions', async (req: Request, res: Response) => {
    const request = req.body as ChatCompletionRequest;
    const oaiRequest = { ...request };

    if (oaiRequest.user_id) {
      oaiRequest.user = oaiRequest.user_id;
      delete oaiRequest.user_id;
    }

    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    try {
      // Send initial buffer chunk while processing
      const initialChunk = {
        id: 'chatcmpl-buffer',
        object: 'chat.completion.chunk',
        created: Math.floor(Date.now() / 1000),
        model: request.model,
        choices: [
          {
            delta: { content: 'Let me think about that... ' },
            index: 0,
            finish_reason: null,
          },
        ],
      };
      res.write(`data: ${JSON.stringify(initialChunk)}\n\n`);

      // Process the actual LLM response
      const stream = await openai.chat.completions.create({
        ...oaiRequest,
        stream: true,
      });

      for await (const chunk of stream) {
        res.write(`data: ${JSON.stringify(chunk)}\n\n`);
      }

      res.write('data: [DONE]\n\n');
      res.end();
    } catch (error) {
      console.error('An error occurred:', error);
      res.write(`data: ${JSON.stringify({ error: 'Internal error occurred!' })}\n\n`);
      res.end();
    }
  });
  ```
</CodeBlocks>

## System tools integration

Your custom LLM can trigger [system tools](/docs/eleven-agents/customization/tools/system-tools) to control conversation flow and state. These tools are automatically included in the `tools` parameter of your chat completion requests when configured in your agent.

### How system tools work

1. **LLM Decision**: Your custom LLM decides when to call these tools based on conversation context
2. **Tool Response**: The LLM responds with function calls in standard OpenAI format
3. **Backend Processing**: ElevenLabs processes the tool calls and updates conversation state

For more information on system tools, please see [our guide](/docs/eleven-agents/customization/tools/system-tools)

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

  <Accordion title="Transfer to human">
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

    Learn more: [Transfer to human tool](/docs/eleven-agents/customization/tools/system-tools/transfer-to-number)
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

### Example Request with System Tools

When system tools are configured, your custom LLM will receive requests that include the tools in the standard OpenAI format:

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant. You have access to system tools for managing conversations."
    },
    {
      "role": "user",
      "content": "I think we're done here, thanks for your help!"
    }
  ],
  "model": "your-custom-model",
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": true,
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "end_call",
        "description": "Call this function to end the current conversation when the main task has been completed...",
        "parameters": {
          "type": "object",
          "properties": {
            "reason": {
              "type": "string",
              "description": "The reason for the tool call."
            },
            "message": {
              "type": "string",
              "description": "A farewell message to send to the user along right before ending the call."
            }
          },
          "required": ["reason"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "language_detection",
        "description": "Change the conversation language when the user expresses a language preference explicitly...",
        "parameters": {
          "type": "object",
          "properties": {
            "reason": {
              "type": "string",
              "description": "The reason for the tool call."
            },
            "language": {
              "type": "string",
              "description": "The language to switch to. Must be one of language codes in tool description."
            }
          },
          "required": ["reason", "language"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "skip_turn",
        "description": "Skip a turn when the user explicitly indicates they need a moment to think...",
        "parameters": {
          "type": "object",
          "properties": {
            "reason": {
              "type": "string",
              "description": "Optional free-form reason explaining why the pause is needed."
            }
          },
          "required": []
        }
      }
    }
  ]
}
```

<Note>
  Your custom LLM must support function calling to use system tools. Ensure your model can generate
  proper function call responses in OpenAI format.
</Note>

# Additional Features

<Accordion title="Custom LLM Parameters">
  You may pass additional parameters to your custom LLM implementation.

  <Tabs>
    <Tab title="Python">
      <Steps>
        <Step title="Define the Extra Parameters">
          Create an object containing your custom parameters:

          ```python
          from elevenlabs.conversational_ai.conversation import Conversation, ConversationConfig

          extra_body_for_convai = {
              "UUID": "123e4567-e89b-12d3-a456-426614174000",
              "parameter-1": "value-1",
              "parameter-2": "value-2",
          }

          config = ConversationConfig(
              extra_body=extra_body_for_convai,
          )
          ```
        </Step>

        <Step title="Update the LLM Implementation">
          Modify your custom LLM code to handle the additional parameters:

          ```python
          import json
          import os
          import fastapi
          from fastapi.responses import StreamingResponse
          from fastapi import Request
          from openai import AsyncOpenAI
          import uvicorn
          import logging
          from dotenv import load_dotenv
          from pydantic import BaseModel
          from typing import List, Optional

          # Load environment variables from .env file
          load_dotenv()

          # Retrieve API key from environment
          OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
          if not OPENAI_API_KEY:
              raise ValueError("OPENAI_API_KEY not found in environment variables")

          app = fastapi.FastAPI()
          oai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

          class Message(BaseModel):
              role: str
              content: str

          class ChatCompletionRequest(BaseModel):
              messages: List[Message]
              model: str
              temperature: Optional[float] = 0.7
              max_tokens: Optional[int] = None
              stream: Optional[bool] = False
              user_id: Optional[str] = None
              elevenlabs_extra_body: Optional[dict] = None

          @app.post("/v1/chat/completions")
          async def create_chat_completion(request: ChatCompletionRequest) -> StreamingResponse:
              oai_request = request.dict(exclude_none=True)
              print(oai_request)
              if "user_id" in oai_request:
                  oai_request["user"] = oai_request.pop("user_id")

              if "elevenlabs_extra_body" in oai_request:
                  oai_request.pop("elevenlabs_extra_body")

              chat_completion_coroutine = await oai_client.chat.completions.create(**oai_request)

              async def event_stream():
                  try:
                      async for chunk in chat_completion_coroutine:
                          chunk_dict = chunk.model_dump()
                          yield f"data: {json.dumps(chunk_dict)}\n\n"
                      yield "data: [DONE]\n\n"
                  except Exception as e:
                      logging.error("An error occurred: %s", str(e))
                      yield f"data: {json.dumps({'error': 'Internal error occurred!'})}\n\n"

              return StreamingResponse(event_stream(), media_type="text/event-stream")

          if __name__ == "__main__":
              uvicorn.run(app, host="0.0.0.0", port=8013)
          ```
        </Step>
      </Steps>

      ### Example Request

      With this custom message setup, your LLM will receive requests in this format:

      ```json
      {
        "messages": [
          {
            "role": "system",
            "content": "\n  <Redacted>"
          },
          {
            "role": "assistant",
            "content": "Hey I'm currently unavailable."
          },
          {
            "role": "user",
            "content": "Hey, who are you?"
          }
        ],
        "model": "gpt-4o",
        "temperature": 0.5,
        "max_tokens": 5000,
        "stream": true,
        "elevenlabs_extra_body": {
          "UUID": "123e4567-e89b-12d3-a456-426614174000",
          "parameter-1": "value-1",
          "parameter-2": "value-2"
        }
      }
      ```
    </Tab>
  </Tabs>
</Accordion>
