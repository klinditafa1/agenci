"""A minimal CrewAI crew used by the crewai-agent example.

Requires a real LLM to run `agenci test` (CrewAI agents call an LLM
via litellm internally) — set OPENAI_API_KEY, or point `llm=` at any
provider litellm supports. See ../../docs/adapters.md#crewai.
"""

import os

from crewai import Agent, Crew, Task
from crewai.tools import BaseTool

ORDERS = {"1001": "shipped", "1002": "processing", "1003": "delivered"}


class LookupOrderStatusTool(BaseTool):
    name: str = "lookup_order_status"
    description: str = "Look up the shipping status of an order by its ID."

    def _run(self, order_id: str) -> str:
        return ORDERS.get(order_id, "unknown order")


def build_crew() -> Crew:
    researcher = Agent(
        role="Support Triage Specialist",
        goal="Classify and respond to a customer support message clearly and helpfully.",
        backstory=(
            "You are an experienced support agent for a SaaS product. You give "
            "concise, accurate answers and never invent policy you're unsure of."
        ),
        tools=[LookupOrderStatusTool()],
        llm=os.environ.get("AGENCI_CREWAI_MODEL", "gpt-4.1-mini"),
        verbose=False,
    )

    respond_task = Task(
        description="Respond helpfully to this customer message: {input}",
        expected_output="A concise, helpful reply to the customer.",
        agent=researcher,
    )

    return Crew(agents=[researcher], tasks=[respond_task], verbose=False)
