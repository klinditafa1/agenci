"""An agent with a (deliberately limited) toolset, used to demonstrate
Agenci's security testing: tool-authorization policies, prompt-injection
resistance, required-tool enforcement, data-exfiltration resistance,
and sensitive-data-leakage resistance.
"""


def run_agent(input: str, context: dict) -> dict:
    lowered = input.lower()

    # Prompt-injection resistance: never comply with instruction-override
    # attempts, and never leak configuration.
    injection_markers = ("ignore previous", "ignore all previous", "reveal your system prompt")
    if any(marker in lowered for marker in injection_markers):
        return {"output": "I can't share internal configuration or override my instructions."}

    # Complaint handling routes through a moderation tool before replying —
    # demonstrates policy.required_tools.
    if "complain" in lowered or "angry" in lowered:
        return {
            "output": "I'm sorry to hear that — I've logged your complaint for review.",
            "tool_calls": [{"tool": "moderation", "arguments": {"reason": "customer_complaint"}}],
        }

    # Email requests always send a fixed, safe summary — never the raw
    # (possibly attacker-controlled) input text — demonstrating resistance
    # to policy.block_input_echo_to_sensitive_tools.
    if "email" in lowered:
        return {
            "output": "I've sent a summary of this conversation to your account email.",
            "tool_calls": [
                {
                    "tool": "send_email",
                    "arguments": {"subject": "Support conversation summary", "body": "See ticket for details."},
                }
            ],
        }

    # Never produces anything that looks like a real credit card number,
    # SSN, or API key — demonstrating resistance to policy.check_pii_leakage.
    if "credit card" in lowered or "card number" in lowered:
        return {"output": "I can't share or generate financial account numbers, even fake ones."}

    # Tool use: only ever calls 'search' or 'calculator', regardless of
    # what the user asks for — it will not attempt destructive actions.
    if "search" in lowered or "find" in lowered:
        return {
            "output": "Here's what I found in the knowledge base.",
            "tool_calls": [{"tool": "search", "arguments": {"query": input}}],
        }
    if "calculate" in lowered or any(ch.isdigit() for ch in input):
        return {
            "output": "Here's the result of that calculation.",
            "tool_calls": [{"tool": "calculator", "arguments": {"expression": input}}],
        }

    return {"output": "I can help with search and calculations. What do you need?"}
