# Contributing to Agenci

Thanks for considering a contribution. Agenci is early-stage and the
architecture is still settling, so an issue before a large PR is
appreciated — but small fixes, docs improvements, and new
adapters/evaluators/examples are welcome directly as PRs.

## Development setup

```bash
git clone https://github.com/agenci-dev/agenci
cd agenci
pip install -e ".[dev]"
```

## Before opening a PR

```bash
ruff check agenci tests
ruff format --check agenci tests
pyright agenci
pytest tests/ -v
```

All four must pass. The project's CI (`.github/workflows/ci.yml`) runs
the same checks across Python 3.10–3.12, plus a CLI smoke test
(`agenci init && agenci test`) and every example in `examples/`.

## Guidelines

- **No paid API calls in tests.** Mock external providers (see
  `tests/unit/test_http_adapter.py` for the `respx` pattern used for
  HTTP, and `agenci/evaluators/mock.py` for why the default judge is a
  deterministic mock). A new adapter or judge provider needs a test
  that runs without a real API key.
- **No fake or partial integrations.** If something can't be built
  correctly yet, add the abstraction (a `Protocol` method, a config
  field) and document the limitation instead of a half-working code
  path — see [docs/extending-agenci.md](docs/extending-agenci.md).
- **Every example must actually run.** `examples/*/README.md` gives
  the exact command; the CI `examples` job runs it.
- **Keep the CLI the primary interface.** The dashboard
  (`agenci/dashboard/`) is intentionally simple — significant frontend
  work is out of scope for the open-source project.
- **Type hints + docstrings** on public functions/classes, especially
  anything in a `Protocol` (`AgentAdapter`, `JudgeProvider`,
  `StorageBackend`) since those are the extension points other
  contributors build against.

## Adding an adapter, judge provider, or assertion type

See [docs/extending-agenci.md](docs/extending-agenci.md) — each of
these has a documented, minimal extension path.

## Reporting bugs

Open a GitHub issue with:
- Your `agenci.yaml` (redact secrets/URLs if needed)
- The command you ran and its full output
- `agenci version` and your Python version

## Security issues

Do not open a public issue for a security vulnerability in Agenci
itself — see [SECURITY.md](SECURITY.md) for how to report it privately.

## Releasing a new version (maintainers)

1. Bump `version` in `pyproject.toml` and `__version__` in
   `agenci/__init__.py` to match.
2. Add a new section to [CHANGELOG.md](CHANGELOG.md) (move
   `[Unreleased]` items under it) and update the "Versioning" note at
   the bottom if this changes anything about the versioning policy.
3. Merge that as a normal PR, then create a GitHub Release with tag
   `vX.Y.Z` matching the version you just set.
4. `.github/workflows/publish.yml` builds the package, verifies the
   tag matches `pyproject.toml`'s version (fails the release if not),
   smoke-tests the built wheel in a clean venv
   (`agenci init && agenci test`), and publishes to PyPI via [Trusted
   Publishing](https://docs.pypi.org/trusted-publishers/) — no
   long-lived PyPI token is stored in this repository.
5. The trusted publisher must be configured once, out-of-band, at
   `https://pypi.org/manage/project/agenci/settings/publishing/`
   (repository: `agenci-dev/agenci`, workflow: `publish.yml`,
   environment: `pypi`).

## License

By contributing, you agree your contributions are licensed under the
project's [Apache 2.0 license](LICENSE).
