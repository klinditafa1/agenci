"""A small, curated library of regex patterns for common sensitive-data
shapes, used by the ``check_pii_leakage`` security policy option.

Deliberately conservative: these patterns favor low false-positive
rates over exhaustive coverage. This is a heuristic scan for obviously
sensitive-looking strings in agent output, not a substitute for a
dedicated DLP/PII-detection system — see docs/security.md.
"""

from __future__ import annotations

# name -> (regex, human-readable description)
SENSITIVE_DATA_PATTERNS: dict[str, tuple[str, str]] = {
    "credit_card": (
        r"\b(?:\d[ -]*?){13,16}\b",
        "a sequence of digits shaped like a credit card number",
    ),
    "us_ssn": (
        r"\b\d{3}-\d{2}-\d{4}\b",
        "a US Social Security Number-shaped value",
    ),
    "aws_access_key": (
        r"\bAKIA[0-9A-Z]{16}\b",
        "an AWS access key ID",
    ),
    "generic_secret_key": (
        r"\b(?:sk|pk|api|key|secret)[-_][A-Za-z0-9]{16,}\b",
        "a string shaped like an API key or secret token",
    ),
    "private_key_header": (
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
        "a PEM private key header",
    ),
    "jwt_like": (
        r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
        "a string shaped like a JWT",
    ),
}
