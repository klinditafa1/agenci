from __future__ import annotations

from agenci.config.models import CostConfig, PricingEntry
from agenci.core.cost import CostEstimator


def test_default_pricing_known_model() -> None:
    estimator = CostEstimator()
    cost = estimator.estimate_usd("gpt-4o-mini", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 0.15 + 0.60


def test_unknown_model_returns_none() -> None:
    estimator = CostEstimator()
    assert estimator.estimate_usd("totally-unknown-model", 100, 100) is None


def test_user_override_takes_precedence() -> None:
    config = CostConfig(models={"gpt-4o-mini": PricingEntry(input_per_1m=99.0, output_per_1m=1.0)})
    estimator = CostEstimator(config)
    cost = estimator.estimate_usd("gpt-4o-mini", input_tokens=1_000_000, output_tokens=0)
    assert cost == 99.0


def test_custom_model_can_be_added() -> None:
    config = CostConfig(models={"my-local-model": PricingEntry(input_per_1m=0.0, output_per_1m=0.0)})
    estimator = CostEstimator(config)
    assert estimator.estimate_usd("my-local-model", 1000, 1000) == 0.0
