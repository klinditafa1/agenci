# Regression testing

The core CI use case: run a "known good" version of your agent, save
it as a baseline, then compare every subsequent run against it.

```text
Developer changes AI agent
        ↓
opens Pull Request
        ↓
Agenci runs evaluations
        ↓
Agenci compares against baseline
        ↓
Agenci detects regressions
        ↓
PR passes or fails
```

## Workflow

```bash
# On main, after a release you trust:
agenci test --save-baseline

# On a feature branch, after making a change:
agenci test
agenci diff --baseline <baseline-run-id>
```

Find a run's ID with `agenci report` (lists recent runs) or
`agenci report --json`.

`--baseline` and `--current` (for `agenci diff`) each accept either a
stored `run_id` or a path to a JSON report file (e.g. one downloaded
from a previous CI run's artifacts) — useful when your baseline was
produced on a different machine.

## What gets compared

| Metric | Regresses when |
|---|---|
| Task success rate | Drops by more than `thresholds.regression.max_drop` (relative), **or** falls below `thresholds.success_rate` (absolute floor) |
| Security score | Same two checks, against `thresholds.security_score` |
| Latency | Increases by more than `thresholds.max_latency_increase` (relative) |
| Cost | Increases by more than `thresholds.max_cost_increase` (relative) |
| Each security category | Drops by more than `thresholds.regression.max_drop` (relative) — catches one category regressing even when the *overall* security score stays within tolerance because another category improved |

Beyond those aggregate/category metrics, every `RegressionReport` also
includes **per-test** analytics, always populated (not just when
something fails), so you can see exactly what changed rather than only
a percentage:

- `newly_failing` — tests that passed in the baseline and fail now.
- `newly_passing` — tests that failed in the baseline and pass now.
- `tests_added` / `tests_removed` — tests present in only one of the
  two runs (e.g. you added a test case on this branch).

By default, individual test flips only affect the `PASS`/`FAIL`
verdict through the aggregate success-rate threshold above — a single
newly-failing test in a 200-test suite might not move the aggregate
rate enough to fail the run. Set
`thresholds.regression.fail_on_any_newly_failing: true` to fail
`agenci diff` whenever **any** specific test regresses, regardless of
the aggregate:

```yaml
thresholds:
  regression:
    max_drop: 0.05
    fail_on_any_newly_failing: true
```

## Example output

```text
Agenci Regression Report

┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ Metric         ┃ Baseline ┃ Current ┃               Delta ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ Task success   │   1.0000 │  0.3333 │    -0.6667 (-66.7%) │
│ Security score │ 100.0000 │  0.0000 │ -100.0000 (-100.0%) │
│ Latency (ms)   │   0.0000 │  0.0000 │             +0.0000 │
│ Cost (USD)     │   0.0000 │  0.0000 │             +0.0000 │
└────────────────┴──────────┴─────────┴─────────────────────┘

Security category deltas
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Category         ┃ Baseline ┃ Current ┃            Delta ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ prompt_injection │      100 │       0 │ -100.0 (-100.0%) │
└──────────────────┴──────────┴─────────┴──────────────────┘

2 test(s) newly failing:
  ✗ refund_request
  ✗ resists_prompt_injection

STATUS: FAIL

  - Task success dropped 66.7% (limit 5%)
  - Security score dropped 100.0% (limit 5%)
  - Task success rate 33.3% is below the configured minimum 90%
  - Security score 0 is below the configured minimum 90
  - Security category 'prompt_injection' dropped 100.0% (limit 5%)
```

`agenci diff` exits `1` on `FAIL`, `0` on `PASS` — plug it directly
into a CI gate. See [examples/regression-testing](../examples/regression-testing)
for a runnable version of the above.

## Configuring thresholds

```yaml
thresholds:
  success_rate: 0.90
  security_score: 0.90
  max_cost_increase: 0.20
  max_latency_increase: 0.25
  regression:
    max_drop: 0.05
    fail_on_any_newly_failing: false   # set true to fail on any single regressed test
```

See [configuration.md](configuration.md#thresholds) for the full
reference.

## Choosing a regression suite

Your `tests/regression.yaml` (or wherever you point `tests.directories`)
should be a **stable, representative sample of real user inputs** —
not just happy-path smoke tests. The more representative it is, the
more a drop in success rate actually means something changed for real
users.
