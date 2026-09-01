"""A minimal MCP server exposing one tool, used by the mcp-agent example.

Run standalone for manual testing:
    python server.py
Agenci launches this itself (see agenci.yaml: agent.mcp_command) — you
don't need to run it separately for `agenci test`.
"""

from mcp.server.fastmcp import FastMCP

server = FastMCP("order-status-server")

ORDERS = {
    "1001": "shipped",
    "1002": "processing",
    "1003": "delivered",
}


@server.tool()
def order_status(order_id: str) -> str:
    """Look up the shipping status of an order by its ID."""
    return ORDERS.get(order_id, "unknown order")


if __name__ == "__main__":
    server.run(transport="stdio")
