"""A small support-triage agent used by the basic-agent example.

Run with:
    cd examples/basic-agent
    agenci test
"""

FAQ = {
    "refund": "I've started a refund for your order; it should appear within 5-7 business days.",
    "cancel": "Your subscription has been cancelled effective at the end of the billing period.",
    "password": "You can reset your password from the account settings page under 'Security'.",
}


def run_agent(input: str, context: dict) -> str:
    lowered = input.lower()
    for keyword, reply in FAQ.items():
        if keyword in lowered:
            return reply
    return "I'm not sure about that yet, but I've logged your question for a human to follow up."
