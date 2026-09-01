# Example: github-actions

A minimal repo showing how to wire Agenci into GitHub Actions using the
official composite action at `action/action.yml` in this repository.

## What to look at

- `.github/workflows/agenci.yaml` — runs `agenci test` and `agenci
  security` on every pull request and push to `main`, uploads the JSON
  reports as workflow artifacts, and fails the check if either command
  exits non-zero (i.e. tests fail, or a threshold in `agenci.yaml` is
  violated).
- `agenci.yaml`, `agent.py`, `tests/` — a minimal project so the
  workflow has something to run; swap these for your real agent.

## Try it locally first

```bash
cd examples/github-actions
agenci test
```

## Using the action in your own repo

```yaml
- uses: actions/checkout@v4
- uses: agenci-dev/agenci/action@v1
  with:
    config: agenci.yaml
    command: both # 'test', 'security', or 'both'
```

See [../../docs/github-actions.md](../../docs/github-actions.md) for
all inputs/outputs and how to fail a PR check on regressions.
