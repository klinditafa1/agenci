"""A small AutoGen agent used by the autogen-agent example.

Uses AutoGen's own `ReplayChatCompletionClient` with pre-scripted
tool-call responses, so `agenci test` runs with no network access or
API key — this exercises the real `autogen-agentchat` agent, tool, and
message machinery, just with a scripted "model" standing in for a real
LLM. Agenci's `autogen` adapter observes the tool call through the
real `ToolCallRequestEvent`/`ToolCallExecutionEvent` messages AutoGen
emits, not by parsing the output text.

Note: because the model is scripted, the responses are matched to
tests/basic.yaml by position, not by actually reading the input text —
see the README for what that does and doesn't verify.
"""

from autogen_agentchat.agents import AssistantAgent
from autogen_core import FunctionCall
from autogen_core.models import CreateResult, RequestUsage
from autogen_core.tools import FunctionTool
from autogen_ext.models.replay import ReplayChatCompletionClient

ORDERS = {
    "1001": "shipped",
    "1002": "processing",
    "1003": "delivered",
}


def lookup_order_status(order_id: str) -> str:
    """Look up the shipping status of an order by ID."""
    return ORDERS.get(order_id, "unknown order")


def _scripted_tool_call(call_id: str, order_id: str) -> CreateResult:
    return CreateResult(
        finish_reason="function_calls",
        content=[
            FunctionCall(
                id=call_id, name="lookup_order_status", arguments=f'{{"order_id": "{order_id}"}}'
            )
        ],
        usage=RequestUsage(prompt_tokens=40, completion_tokens=8),
        cached=False,
    )


def build_agent() -> AssistantAgent:
    """Factory: Agenci calls this once and reuses the returned agent,
    resetting its conversation state before every test case (see
    agenci/adapters/autogen_adapter.py)."""
    tool = FunctionTool(lookup_order_status, description="Look up order status by id")

    # One scripted response per test case, in the order tests/basic.yaml defines them.
    responses = [
        _scripted_tool_call("call_1", "1001"),  # known_order_status
        _scripted_tool_call("call_2", "9999"),  # unknown_order_status
        _scripted_tool_call("call_3", "1002"),  # only_uses_lookup_tool (security)
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
