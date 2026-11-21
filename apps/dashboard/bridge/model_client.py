"""Unified platform SDK adapter. Uses the same runtime credential path as TTS."""
import json
import asyncio
from types import SimpleNamespace
from pplx.python.sdks.llm_api import (
    Client, Conversation, Identity, LLMAPIClient, SamplingParams,
    TextBlock, Tool, ToolParams, ToolResultBlock, ToolUseBlock,
)

class Block(SimpleNamespace):
    def model_dump(self, **kwargs):
        return vars(self)

class Messages:
    async def create(self, *, model, max_tokens, system, messages, tools=None):
        convo = Conversation()
        convo.set_system(system)
        for message in messages:
            value = message["content"]
            if isinstance(value, list):
                blocks = []
                for item in value:
                    if item["type"] == "text":
                        blocks.append(TextBlock(text=item["text"]))
                    elif item["type"] == "tool_use":
                        blocks.append(ToolUseBlock(id=item["id"], name=item["name"],
                                                   input=json.dumps(item["input"])))
                    elif item["type"] == "tool_result":
                        blocks.append(ToolResultBlock(tool_use_id=item["tool_use_id"],
                            content=[TextBlock(text=item["content"])], is_error=item.get("is_error", False)))
                value = blocks
            if message["role"] == "assistant":
                convo.add_assistant(value, new_message=True)
            else:
                convo.add_user(value, new_message=True)
        kwargs = {"model": model, "convo": convo,
                  "identity": Identity(client=Client.ASI, use_case="webserver_chat"),
                  "sampling_params": SamplingParams(max_tokens=max_tokens)}
        if tools:
            kwargs["tool_params"] = ToolParams(tools=[Tool(**tool) for tool in tools], parallel_tool_calls=False)
        result = await asyncio.wait_for(LLMAPIClient().messages.create(**kwargs), timeout=75)
        blocks = []
        for block in result.content:
            if block.type == "text":
                blocks.append(Block(type="text", text=block.text))
            elif block.type == "tool_use":
                blocks.append(Block(type="tool_use", id=block.id, name=block.name, input=json.loads(block.input)))
        return SimpleNamespace(content=blocks)

class ModelClient:
    def __init__(self, **kwargs):
        self.messages = Messages()
