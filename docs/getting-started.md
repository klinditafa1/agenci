# Getting started

## Install

```bash
pip install agenci
```

Or, without a persistent install:

```bash
uvx agenci init
```

## 1. Scaffold a project

```bash
agenci init
```

This creates:

```text
agenci.yaml
agent.py
tests/
    basic.yaml
    regression.yaml
    security.yaml
.github/workflows/agenci.yaml
```

`agent.py` is a tiny example agent so `agenci test` works immediately.
Point `agenci.yaml` at your real agent when you're ready — see
[adapters.md](adapters.md).

## 2. Run the test suite

```bash
agenci test
```

```text
Agenci — my-agent
2 evaluations completed

┏━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━┓
┃ Suite      ┃ Passed ┃ Total ┃ Status ┃
┡━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━┩
│ Functional │ 2      │ 2     │ PASS   │
└────────────┴────────┴───────┴────────┘

Success rate:   100.0%
Security score: 100/100
Estimated cost: $0.0000

STATUS: PASS
```

Exit code is `0` on pass, `1` on fail — this is what CI uses to block
a PR.

## 3. Run security tests

```bash
agenci security
```

Runs only `type: security` test cases and prints a security score
broken down by category. See [security.md](security.md).

## 4. Catch regressions

```bash
agenci test --save-baseline   # mark this run as the baseline
# ...make a change to your agent...
agenci test                   # run again
agenci diff --baseline <run-id-from-the-first-run>
```

`agenci report` lists recent run IDs. See
[regression-testing.md](regression-testing.md).

## 5. Wire it into CI

```bash
cat .github/workflows/agenci.yaml
```

Already scaffolded by `agenci init`. See [github-actions.md](github-actions.md).

## Next steps

- [Write your own tests](tests.md)
- [Add LLM-as-judge evaluation](evaluations.md)
- [Point Agenci at your real agent](adapters.md)
- [Configuration reference](configuration.md)
