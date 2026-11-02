# Testing and code quality

## Current verified test status — 31 October 2026

The full suite completed with **613 passed in 5.58s**, with no failures, skips,
or expected failures. The command executed from the repository root was:

```sh
PYTHONDONTWRITEBYTECODE=1 pytest -v -p no:cacheprovider
```

This includes `tests/test_process_persistence.py`, which writes a real Flask
assignment run in one Python process and retrieves the complete snapshot and
recomputed metrics in another after the writer exits. Both processes use only
a disposable SQLite file; integrity/FK checks and cleanup are asserted.
The focused command returned **1 passed in 0.98s**:

```sh
PYTHONDONTWRITEBYTECODE=1 pytest -v -p no:cacheprovider tests/test_process_persistence.py
```

| Required category | Representative automated tests |
| --- | --- |
| Component | `test_contract_and_engine.py`, `test_solution_metrics.py`, `test_visualization_component.py` |
| Database | `test_persistence.py`, `test_database_validation.py`, `test_process_persistence.py` |
| Integration | `test_component_integration.py`, `test_team_b_application.py`, `test_engine_execution.py` |
| Edge cases | `test_edge_cases.py` (15 numbered cases), `test_bilp_feasibility.py`, `test_bilp_alternatives.py` |

All modules are under `tests/` and are included by the full-suite command.
See [the integration verification](team_b_integration_verification.md) for
restart evidence and historical results. Solver status/interruption tests use
simulated outcomes, not a demonstrated CBC wall-clock timeout. Historical input
snapshots remain open (DB-04 in the validation checklist). Ruff lint and format
checks passed for the new test only; project-wide quality checks were not rerun.

## Historical validation-branch status — 21 October 2026

On 21 October 2026, the full suite completed with:

```text
4 failed, 440 passed, 12 xfailed in 20.04s
```

Command: `python -m pytest -q`, using the project's virtual environment and
access to pytest's temporary SQLite databases. There are 456 test examples.

The four failures are the parameterized
`test_real_engine_accepts_capacity_boundaries` cases in
`tests/test_solvers.py`: zero minimum, minimum boundary, maximum boundary,
and equal bounds. Each reaches `AssignmentEngine.execute_run()`, which raises
`NotImplementedError`. No actual assignment assertions are reached.

The user explicitly limited this change to refactoring and deferred solver
implementation to a separate PR. The four failing cases and their assertions
remain unchanged. That historical run did **not** satisfy a passing-suite merge gate.

All 12 expected-failure markers, including their reasons and exception
conditions, match the freshly fetched `origin/main` at `023e00e`. No new
xfails or skips were added. Expected failures represent unfinished work.

The refactor passed these checks across `app`, `tests`, and `run.py`:

- Ruff lint: Google docstrings, function annotations, import order, unused
  imports, and line length.
- Ruff formatting.
- A separate physical-line check: no Python line exceeds 80 characters,
  including type-ignore comments.
- Executable AST comparison against the pre-refactor branch: no changes after
  accounting for import cleanup, docstrings, and one shortened test name.

The AST check supplements the tests; it does not prove that the unfinished
solver or scoring methods work. Tests were not removed, weakened, or converted
to mocks to obtain a green result.

## Development setup and repeatable checks

Run these commands in PowerShell from the repository directory:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m ruff check app tests run.py
python -m ruff format --check app tests run.py
python -m pytest -q
```

Activation selects the project's Python environment. Ruff is a development
dependency pinned in `requirements-dev.txt`; runtime requirements are unchanged.
The rules are configured in `pyproject.toml`.

To apply formatting before checking again:

```powershell
python -m ruff format app tests run.py
```

Google-style docstrings describe purpose, parameters under `Args:`, return
values under `Returns:` or `Yields:`, and relevant exceptions under `Raises:`.
A short descriptive test may use a single-line docstring. Type annotations
describe parameter and return types; they do not replace runtime validation.

Do not check a PR's passing-tests box after a partial run or a
`KeyboardInterrupt`. Let the full command finish and report its actual summary.
Use the current completed run when reporting the passing-tests status.

## Responsibilities and behaviour preserved

| Component | Responsibility |
| --- | --- |
| Domain objects | Represent students, projects, preferences, and fixed assignments. |
| Domain validation functions | Apply stateless type, reference, range, and feasibility rules. |
| Form objects | Parse submitted strings and collect field errors before saving. |
| Engine objects | Expose the shared component interface and coordinate runs. |
| Repositories | Map domain objects to SQLite records. |
| Database manager | Own connections and shared transaction boundaries. |
| Flask routes | Coordinate requests, validation, persistence, and responses. |

The design already separates stateful objects from stateless validation.
Formatting and documentation do not require wrapping those functions in
additional classes. Database schema, public interfaces, rejection messages,
rollback behaviour, and explicit mock workflows are preserved.

## Validation evidence and manual testing

Use [the validation walkthrough](validation_walkthrough.md) for the code and
test catalogue, and [the checklist](input_output_validation_checklist.md) for
implemented policies and unfinished cases.

Unit tests cover domain validation and form parsing. Contract tests check
diagnostics returned to Team A. Flask-client and SQLite tests cover rejected
requests, preserved records, and rollback after write failures. Mock workflow
tests establish UI integration; they do not establish real solver correctness.

No manual browser testing was performed as part of this refactor. Record
manual steps and observed results separately from automated client tests.
AI assisted with the formatting, documentation, and verification; student
understanding and teammate review are not established by these checks.
