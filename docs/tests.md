# Writing tests

Test cases live in YAML files under the directories listed in
`tests.directories` (default `tests/`). A file can hold one test case
(a mapping), a list of test cases, or `{"tests": [...]}`:

```yaml
tests:
  - name: cancellation_request
    type: functional
    input: "I want to cancel my subscription."
    assertions:
      - contains: "cancellation"
      - not_contains: "I cannot help"
```

## Fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | required | Unique within your suite; shown in reports. |
| `type` | `functional` \| `security` | `functional` | Security tests also count toward the security score — see [security.md](security.md). |
| `category` | string | none | Free-form label for security tests (`prompt_injection`, `tool_authorization`, ...). |
| `input` | string | required | Sent to the agent as-is. |
| `context` | map | `{}` | Passed through to your adapter alongside `input`. |
| `assertions` | list[Assertion] | `[]` | See below. |
| `evaluation` | EvaluationSpec | none | LLM-as-judge scoring — see [evaluations.md](evaluations.md). |
| `policy` | SecurityPolicy | none | Tool-authorization policy — see [security.md](security.md). |
| `tags` | list[string] | `[]` | Free-form, for your own filtering/organization. |

A test passes only if **every** assertion, **every** evaluator
criterion, and **every** security-policy check passes.

## Assertions

Each item in `assertions` sets exactly one of the following keys:

| Key | Checks | Example |
|---|---|---|
| `contains` | Output contains a substring. | `contains: "refund"` |
| `not_contains` | Output does not contain a substring. | `not_contains: "I cannot help"` |
| `regex` | Output matches a regex (`re.search`). | `regex: 'order #\d+'` |
| `exact` | Output equals a string exactly. | `exact: "OK"` |
| `json_schema` | Output is valid JSON matching a [JSON Schema](https://json-schema.org/). | see below |
| `semantic_similarity` | Output is semantically similar to reference text, per the configured judge. | see below |
| `custom_python` | A Python function you write. | `custom_python: "checks:is_valid_email"` |

### `json_schema`

```yaml
assertions:
  - json_schema:
      type: object
      required: [order_id, status]
      properties:
        order_id: { type: string }
        status: { type: string, enum: [pending, shipped, delivered] }
```

### `semantic_similarity`

Requires a configured judge (`evaluation.judge` in `agenci.yaml`).

```yaml
assertions:
  - semantic_similarity: "Your refund has been processed."
    similarity_threshold: 0.75   # default 0.75
```

### `custom_python`

`module.path:function_name`, resolved relative to your project
directory (which Agenci adds to `sys.path`). The function receives the
agent's output string and returns either a `bool`, or a `(bool, str)`
tuple where the string explains a failure:

```python
# checks.py
def is_valid_email(output: str) -> tuple[bool, str]:
    import re
    ok = bool(re.search(r"[^@]+@[^@]+\.[^@]+", output))
    return ok, "" if ok else "Output did not contain a valid email address"
```

```yaml
assertions:
  - custom_python: "checks:is_valid_email"
```

## Organizing tests

Any file layout under `tests.directories` works — Agenci discovers
`*.yaml`/`*.yml` files recursively. A common pattern:

```text
tests/
    basic.yaml         # smoke tests
    regression.yaml     # representative real inputs, used as a diff baseline
    security.yaml       # security policy tests
```

See [regression-testing.md](regression-testing.md) for why
`regression.yaml`-style suites matter.
