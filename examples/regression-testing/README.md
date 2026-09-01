# Example: regression-testing

Demonstrates `agenci diff`: run the "good" version of an agent as a
baseline, simulate a regression, then detect it.

## Run it

```bash
cd examples/regression-testing

# 1. Establish a baseline on the known-good version.
agenci test --save-baseline

# 2. Grab the baseline run_id.
RUN_ID=$(agenci report --json | python3 -c \
  "import json,sys; print([r['run_id'] for r in json.load(sys.stdin) if r['is_baseline']][0])")

# 3. Simulate a regression (see agent.py) and run again.
AGENCI_EXAMPLE_VERSION=v2 agenci test

# 4. Compare.
agenci diff --baseline "$RUN_ID"
```

`agenci diff` exits non-zero and prints which metrics regressed and by
how much — this is exactly the check a CI pipeline runs on every pull
request.

## What to look at

- `agent.py` — `AGENCI_EXAMPLE_VERSION=v2` simulates a regression: a
  functional test that used to pass starts failing, and a
  prompt-injection test that used to pass starts failing too.
- `agenci.yaml` — `thresholds.regression.max_drop` controls how large a
  drop in success rate or security score is tolerated before `agenci
  diff` fails.
- See [../../docs/regression-testing.md](../../docs/regression-testing.md).
