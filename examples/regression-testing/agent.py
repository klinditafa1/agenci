"""Two versions of the same agent, used to demonstrate `agenci diff`.

Set AGENCI_EXAMPLE_VERSION=v2 to simulate a change that regresses
correctness and security — this is what `agenci diff` is designed to
catch before it reaches production.
"""

import os

VERSION = os.environ.get("AGENCI_EXAMPLE_VERSION", "v1")


def run_agent(input: str, context: dict) -> str:
    lowered = input.lower()

    if VERSION == "v2":
        # Simulated regression: v2 got chattier and started echoing
        # untrusted input directly into its reply, which a prompt
        # injection test would catch.
        if "ignore" in lowered and "instructions" in lowered:
            return f"Sure! {input}"
        if "refund" in lowered:
            return "Sorry, I cannot help with that right now."  # regressed: used to help
        return f"Thanks for your message: {input}"

    if "refund" in lowered:
        return "I've started your refund; it should land within 5-7 business days."
    if "ignore" in lowered and "instructions" in lowered:
        return "I can't ignore my instructions."
    return "Thanks for reaching out! How can I help?"
