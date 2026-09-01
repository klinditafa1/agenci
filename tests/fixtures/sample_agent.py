"""A tiny fixture agent used across the test suite."""

import asyncio
import time


def run_agent(input: str, context: dict) -> str:
    if "cancel" in input.lower():
        return "Your subscription has been cancelled."
    if "ignore" in input.lower() and "instructions" in input.lower():
        return "I can't ignore my instructions."
    return f"ack: {input}"


def agent_with_tools(input: str, context: dict) -> dict:
    if "delete" in input.lower():
        return {
            "output": "I used the shell tool to delete files.",
            "tool_calls": [{"tool": "shell", "arguments": {"cmd": "rm -rf /"}}],
        }
    return {
        "output": "Searched and found nothing relevant.",
        "tool_calls": [{"tool": "search", "arguments": {"query": input}}],
    }


async def async_agent(input: str, context: dict) -> str:
    return f"async ack: {input}"


class FactoryAgent:
    def run(self, input: str, context: dict) -> str:
        return f"factory ack: {input}"


def create_agent():
    return FactoryAgent()


def broken_agent(input: str, context: dict) -> str:
    raise RuntimeError("boom")


def build_langchain_chain():
    from langchain_core.runnables import RunnableLambda

    def _run(payload: dict, config=None):
        text = payload.get("input", "")
        return {"output": f"lc-ack: {text}"}

    return RunnableLambda(_run)


def build_langchain_chain_with_tool():
    from langchain_core.runnables import RunnableLambda
    from langchain_core.tools import tool

    @tool
    def word_count(text: str) -> int:
        """Count words in text."""
        return len(text.split())

    def _run(payload: dict, config=None):
        text = payload.get("input", "")
        count = word_count.invoke(text, config=config)
        return {"output": f"{count} words"}

    return RunnableLambda(_run)


def broken_langchain_chain():
    from langchain_core.runnables import RunnableLambda

    def _run(payload: dict, config=None):
        raise RuntimeError("chain exploded")

    return RunnableLambda(_run)


def build_autogen_agent():
    from autogen_agentchat.agents import AssistantAgent
    from autogen_core import FunctionCall
    from autogen_core.models import CreateResult, RequestUsage
    from autogen_core.tools import FunctionTool
    from autogen_ext.models.replay import ReplayChatCompletionClient

    def lookup_order(order_id: str) -> str:
        """Look up an order's status."""
        return "shipped" if order_id == "1001" else "unknown order"

    tool = FunctionTool(lookup_order, description="Look up order status by id")
    responses = [
        CreateResult(
            finish_reason="function_calls",
            content=[FunctionCall(id="call_1", name="lookup_order", arguments='{"order_id": "1001"}')],
            usage=RequestUsage(prompt_tokens=50, completion_tokens=10),
            cached=False,
        ),
        CreateResult(
            finish_reason="function_calls",
            content=[FunctionCall(id="call_2", name="lookup_order", arguments='{"order_id": "1001"}')],
            usage=RequestUsage(prompt_tokens=50, completion_tokens=10),
            cached=False,
        ),
    ]
    client = ReplayChatCompletionClient(
        responses,
        model_info={
            "function_calling": True,
            "vision": False,
            "json_output": False,
            "family": "unknown",
            "structured_output": False,
        },
    )
    return AssistantAgent(name="support_agent", model_client=client, tools=[tool])


def build_broken_autogen_agent():
    class _Broken:
        async def run(self, task):
            raise RuntimeError("agent exploded")

    return _Broken()


def not_an_autogen_agent():
    return object()


async def slow_agent(input: str, context: dict) -> str:
    """An agent with an artificial delay, used to test TestRunner concurrency."""
    delay = (context or {}).get("delay_seconds", 0.08)
    start = time.perf_counter()
    await asyncio.sleep(delay)
    return f"handled '{input}' after {time.perf_counter() - start:.3f}s"
