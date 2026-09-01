# Evaluations (LLM-as-judge)

Some qualities — correctness, helpfulness, factuality, instruction
following — can't be checked with a substring or regex. Agenci's
`evaluation:` block scores those with an LLM judge.

```yaml
tests:
  - name: cancellation_request
    input: "I want to cancel my subscription."
    evaluation:
      type: llm_judge
      criteria:
        - correctness
        - relevance
        - instruction_following
      threshold: 0.80
```

Each criterion gets its own 0-1 score and pass/fail against
`threshold`. A test only passes if every criterion meets the
threshold (in addition to its regular `assertions`, if any).

## Judge providers

Configured once in `agenci.yaml`, used by every test that declares an
`evaluation:` block (and by `semantic_similarity` assertions):

```yaml
evaluation:
  judge:
    provider: mock      # or: openai
    model: gpt-4.1-mini
    api_key_env: OPENAI_API_KEY
    base_url: null       # point at any OpenAI-compatible endpoint
```

### `mock` (default)

A deterministic, dependency-free heuristic judge: it scores based on
output length, refusal-pattern detection, and vocabulary overlap with
the input. It requires no API key and no network access, which is why
it's the default — a brand-new `agenci init && agenci test` works
immediately, in CI, with zero secrets configured.

**The mock judge is a placeholder, not a production evaluator.** Use it
to validate your test suite's plumbing, then switch to `openai` (or a
provider you add — see [extending-agenci.md](extending-agenci.md))
before relying on evaluation scores for real regression detection.

### `openai`

Calls an OpenAI-compatible chat completions API with a judge prompt
and parses a `{"score": ..., "rationale": ...}` response. Requires
`OPENAI_API_KEY` (or your configured `api_key_env`) to be set.

```bash
export OPENAI_API_KEY=sk-...
agenci evaluate
```

## `agenci evaluate`

Runs the full suite and prints a table of every evaluator score,
independent of pass/fail status — useful when iterating on a prompt
and you want to see the numbers move, not just PASS/FAIL:

```bash
agenci evaluate
```

```text
                         Evaluator scores
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┓
┃ Test                 ┃ Criterion   ┃ Score ┃ Threshold ┃ Result ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━┩
│ cancellation_request │ correctness │  0.61 │      0.50 │ PASS   │
│ cancellation_request │ helpfulness │  0.61 │      0.50 │ PASS   │
└──────────────────────┴─────────────┴───────┴───────────┴────────┘
```

## Adding a judge provider

See [extending-agenci.md](extending-agenci.md#adding-a-judge-provider) —
implementing the `JudgeProvider` protocol is the entire surface area.
