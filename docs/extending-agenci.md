# Extending Agenci

Agenci is built around three small `Protocol`s. Implementing one of
them and registering it is the entire surface area for adding a new
adapter, judge provider, or storage backend — see
[architecture.md](architecture.md) for how they fit together.

## Adding an adapter

1. Implement `agenci.adapters.base.AgentAdapter`:

   ```python
   # agenci/adapters/my_framework_adapter.py
   from agenci.adapters.base import AgentResponse

   class MyFrameworkAdapter:
       def __init__(self, **config) -> None:
           ...

       async def run(self, input: str, context: dict | None = None) -> AgentResponse:
           # call your framework, normalize the result
           return AgentResponse(output="...", tool_calls=[...])

       async def aclose(self) -> None:
           ...
   ```

2. Add a config field to `AgentConfig` in `agenci/config/models.py` if
   your adapter needs new options, with a `@model_validator` requiring
   them when your adapter is selected (see the existing `python`/`http`/
   `openai` validation for the pattern).

3. Add one branch to `build_adapter()` in `agenci/adapters/registry.py`.

4. Add tests under `tests/unit/` (mock the framework the same way
   `tests/unit/test_http_adapter.py` mocks HTTP with `respx`) and a
   runnable example under `examples/`.

**Do not** claim an adapter is supported in the README or docs until
it's implemented and tested — see the "What NOT to build" principle in
the project's founding spec: no fake integrations, no unsupported
claims.

## Adding a judge provider

1. Implement `agenci.evaluators.base.JudgeProvider`:

   ```python
   class MyJudge:
       name = "my_judge"

       async def score(
           self, *, input: str, output: str, criterion: str, context: dict | None = None
       ) -> tuple[float, str]:
           # return (score in [0, 1], short rationale)
           ...
   ```

2. Add a case to `JudgeConfig.provider` in `agenci/config/models.py`
   and a branch in `build_judge()` in `agenci/evaluators/engine.py`.

3. Tests: see `tests/unit/test_evaluators.py` for the pattern (the
   `MockJudge` tests are the simplest reference; wrap real API calls in
   `respx`/mocks the way `tests/unit/test_http_adapter.py` does).

## Adding a storage backend

Implement `agenci.storage.base.StorageBackend`
(`save_run`/`get_run`/`list_runs`/`latest_run`/`close`) against
whatever you want to persist to — this is the seam a future Postgres
("Agenci Cloud") backend uses, and the same seam works for a custom
backend of your own. The CLI, dashboard, and reporting layer only ever
call the protocol methods, never `SqliteStorage` directly, so a new
backend is a drop-in swap.

## Adding a new assertion type

1. Add the field to `agenci.core.models.Assertion` and
   `AssertionType`.
2. Add a `check_*` function to `agenci/core/assertions.py` and a
   branch in `run_assertion()`.
3. Document it in [tests.md](tests.md#assertions).

## Code standards

- Type hints everywhere; `pyright agenci` must pass.
- `ruff check agenci tests` and `ruff format --check agenci tests` must
  pass.
- New functionality needs a unit test with a mocked provider — the
  project's own CI (and, per policy, your PR's CI) must never require a
  paid API call to pass.
- Prefer a clean abstraction over a partial feature: if something can't
  be implemented correctly yet, add the seam (a `Protocol` method, a
  config field) and document the limitation rather than leaving a
  half-working code path.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the PR process.
