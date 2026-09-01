"""Centralized, configurable cost estimation.

All pricing logic lives here so it is not scattered across adapters and
evaluators. Prices are approximate, user-overridable, and always
labeled as estimates — Agenci does not claim to reproduce a provider's
exact billing.
"""

from __future__ import annotations

from agenci.config.models import CostConfig, PricingEntry

# A small set of built-in defaults so `agenci test` produces a non-zero
# cost estimate out of the box. Users should override these in
# agenci.yaml (`cost.models`) for accurate figures — see docs/configuration.md.
_DEFAULT_PRICING: dict[str, PricingEntry] = {
    "gpt-4.1-mini": PricingEntry(input_per_1m=0.40, output_per_1m=1.60),
    "gpt-4.1": PricingEntry(input_per_1m=2.00, output_per_1m=8.00),
    "gpt-4o-mini": PricingEntry(input_per_1m=0.15, output_per_1m=0.60),
    "gpt-4o": PricingEntry(input_per_1m=2.50, output_per_1m=10.00),
}


class CostEstimator:
    """Resolves (model -> $/token) and estimates the cost of a call.

    Estimates are ESTIMATES: they are based on user-supplied or
    built-in default per-1M-token prices and do not reflect any
    provider's actual invoice.
    """

    def __init__(self, config: CostConfig | None = None) -> None:
        self._pricing: dict[str, PricingEntry] = dict(_DEFAULT_PRICING)
        if config is not None:
            self._pricing.update(config.models)

    def known_models(self) -> list[str]:
        return sorted(self._pricing)

    def price_for(self, model: str) -> PricingEntry | None:
        return self._pricing.get(model)

    def estimate_usd(self, model: str, input_tokens: int, output_tokens: int) -> float | None:
        """Return an estimated cost in USD, or None if the model is unpriced."""
        entry = self._pricing.get(model)
        if entry is None:
            return None
        return (input_tokens / 1_000_000) * entry.input_per_1m + (
            output_tokens / 1_000_000
        ) * entry.output_per_1m
