"""A small LangChain agent used by the langchain-agent example.

Uses only langchain-core (no network, no API key) so `agenci test`
works immediately: a RunnableLambda that looks up an order status via
a LangChain @tool. Agenci's `langchain` adapter observes the tool call
through LangChain's callback system, not by parsing the output text.
"""

from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool

ORDERS = {
    "1001": "shipped",
    "1002": "processing",
    "1003": "delivered",
}


@tool
def lookup_order_status(order_id: str) -> str:
    """Look up the shipping status of an order by ID."""
    return ORDERS.get(order_id, "unknown order")


def _run(payload: dict, config=None) -> dict:
    text = payload.get("input", "")
    digits = "".join(ch for ch in text if ch.isdigit())

    if digits:
        status = lookup_order_status.invoke(digits, config=config)
        return {"output": f"Order {digits} is currently: {status}."}

    return {"output": "I couldn't find an order number in your message. Could you share it?"}


def build_chain():
    """Factory: Agenci calls this once and reuses the returned Runnable."""
    return RunnableLambda(_run)
