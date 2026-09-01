# GitHub Actions

`agenci init` scaffolds `.github/workflows/agenci.yaml` for you. Two
ways to run Agenci in CI:

## Option A: the official composite action (recommended)

```yaml
name: Agenci

on:
  pull_request:
  push:
    branches: [main]

jobs:
  agenci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: agenci-dev/agenci/action@v1
        with:
          config: agenci.yaml
          command: both # 'test', 'security', or 'both'
```

### Inputs

| Input | Default | Notes |
|---|---|---|
| `config` | `agenci.yaml` | Path to your config file. |
| `command` | `both` | `test`, `security`, or `both`. |
| `python-version` | `3.12` | Python version to install Agenci with. |
| `agenci-version` | latest | Pin a specific `agenci` PyPI version. |
| `working-directory` | `.` | Directory containing `agenci.yaml`. |
| `post-pr-comment` | `true` | Post/update a summary comment on the pull request (see below). |
| `github-token` | `${{ github.token }}` | Token used to post the comment. Needs `pull-requests: write` permission. |

### Outputs

| Output | Meaning |
|---|---|
| `status` | `PASS` or `FAIL`. |
| `report-path` | Path to the JSON test report. |

### Behavior

1. Installs Python + `agenci`.
2. Runs `agenci test` and/or `agenci security` with `--json --output`.
3. Uploads both JSON reports as a `agenci-reports` workflow artifact
   (`if: always()`, so you get the report even on failure).
4. Writes a one-line summary to the GitHub Actions job summary.
5. On `pull_request`/`pull_request_target` events (and when
   `post-pr-comment` isn't set to `false`), posts or updates a summary
   comment on the PR — see below. A failure to post the comment (e.g. a
   token permission issue) doesn't fail the workflow; it only affects
   whether the comment appears.
6. Fails the workflow (non-zero exit) if either command's status was
   `FAIL` — this is what blocks a PR from merging.

## PR comments

By default, the action posts a comment like this on the pull request,
using the same combined status table and verdict shown in the CLI
report:

```text
Agenci — my-agent

5 evaluation(s) completed

| Suite      | Status  |
|------------|---------|
| Functional | ✅ PASS |
| Security   | ✅ PASS |

- Success rate: 100.0%
- Security score: 100/100
- Estimated cost: $0.0000

✅ Agenci checks passed.
```

Re-running the workflow on the same PR **updates the existing comment**
instead of adding a new one each time — Agenci embeds a hidden marker
(`<!-- agenci-report:<project> -->`) and looks for a matching comment
before deciding whether to create or edit.

Requires `pull-requests: write` permission for the token used:

```yaml
permissions:
  pull-requests: write
```

To use it outside the composite action, or to combine a regression
report into the same comment:

```bash
agenci test --json --output report.json
agenci security --json --output security-report.json
agenci diff --baseline <run-id> --json > regression.json

agenci pr-comment \
  --report report.json \
  --security-report security-report.json \
  --regression regression.json
```

`agenci pr-comment` resolves the repo and PR number, in order:
`--repo`/`--pr` flags → `github.repo`/`github.pr_number` in
`agenci.yaml` → auto-detection from `GITHUB_REPOSITORY` and
`GITHUB_EVENT_PATH`/`GITHUB_REF` (the standard GitHub Actions env
vars — no extra configuration needed inside a workflow run). The
token is read from `$GITHUB_TOKEN` by default (`github.token_env` in
`agenci.yaml`, or `--token-env`, to use a different variable).

Use `--dry-run` to print the comment markdown instead of posting it —
useful for previewing locally or in a workflow step that shouldn't
have GitHub API access.

## Security considerations

**Least privilege.** The default `github-token: ${{ github.token }}`
inherits whatever permissions your workflow (or your repository's
default `GITHUB_TOKEN` settings) grants — which can be broader than
`pr-comment` needs. Always scope it explicitly in the calling
workflow:

```yaml
permissions:
  pull-requests: write
  contents: read
```

**Don't use `pull_request_target` to test untrusted PR code.**
`pull_request_target` runs with the *base* repository's token — the
same privileged `GITHUB_TOKEN` this action uses to post comments —
even for PRs from forks. If a workflow on `pull_request_target` also
checks out and executes the PR's own head commit (e.g.
`actions/checkout` with `ref: ${{ github.event.pull_request.head.sha }}`)
before running `agenci test` against that code, an attacker's PR can
run arbitrary code with write access to your repository and secrets —
this is the well-known ["pwn request"](https://securitylab.github.com/resources/github-actions-preventing-pwn-requests/)
pattern, and it is not specific to Agenci: it applies to *any* action
that executes repository code on `pull_request_target`.

- For public repositories accepting external contributions, trigger
  on plain `pull_request` (the default in every Agenci-generated
  workflow and example in this repo) — it runs with a
  read-only-by-default, fork-scoped token, so a malicious agent under
  test can't use Agenci's own token to write back to your repo.
- Only use `pull_request_target` if you are not checking out or
  executing the PR's own head commit (e.g. you're only reading
  metadata), or if you've added a manual approval gate before running
  untrusted code.

**Test inputs and outputs are not sanitized as trusted content.**
`agenci pr-comment` renders test names, assertion details, and error
messages directly into the PR comment's markdown. If your test suite's
`input`/assertions are ever derived from untrusted, external data (for
example, a fuzzer or an upstream service), treat the resulting comment
the same way you'd treat any other rendering of that data: it can
contain arbitrary Markdown, though GitHub's comment renderer already
sanitizes HTML/script content the same way it does for any PR comment.

## Option B: plain steps

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: "3.12"
- run: pip install agenci
- run: agenci test --config agenci.yaml --json --output agenci-report.json
- run: agenci security --config agenci.yaml --json --output agenci-security.json
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: agenci-reports
    path: agenci-*.json
```

Both `agenci test` and `agenci security` already exit non-zero on
failure, so no extra `exit 1` step is needed with Option B either.

## Regression testing in CI

`agenci diff` needs a baseline to compare against. A common pattern:
run `agenci test --save-baseline` on `main` (e.g. in a separate,
scheduled workflow or on every merge to `main`), persist `.agenci/agenci.db`
or the JSON report as a build artifact/cache, then in PR builds run
`agenci diff --baseline path/to/baseline-report.json`. See
[regression-testing.md](regression-testing.md) for the underlying
mechanics — `--baseline`/`--current` both accept a JSON file path, not
just a stored `run_id`, specifically to support cross-job baselines
like this.
