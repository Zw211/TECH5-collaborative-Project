# Team B — Milestone 6 integration verification

**Status:** Integrasjon verifisert mot nåværende applikasjon; endelig integrasjon med Team A gjenstår.

This verifies the application currently on `teamB/build_solver`. It does not
verify unmerged or future Team A changes. No Team A files, shared interfaces,
or production code were modified in this milestone.

## Deliverable 2: relational persistence — 31 October 2026

**Result: PASS.** A disposable SQLite database and the real Flask assignment
engine saved **1 completed run, 3 solutions, and 30 assignments for 10 students**.
The first application process exited, closing its database connections. A
separate Python process created a new Flask application against the same file
and retrieved the complete run, solutions, and assignments. The retrieved run
matched the saved snapshot, including configuration and metrics. Independently
recomputed solution metrics matched the stored indicators; run and solution
pages returned HTTP 200 after restart.

Before and after restart, `PRAGMA foreign_keys` returned 1,
`PRAGMA foreign_key_check` returned no violations, and `PRAGMA integrity_check`
returned `ok`. Attempts to replace assignment solution, student, and project
references with nonexistent IDs raised `sqlite3.IntegrityError`; savepoints
rolled back each probe. Independent allocation checks verified student coverage,
capacity, mandatory requirements, fixed locks, and distinct alternatives.

### Reproduction procedure used

The check ran as `python /tmp/verify_deliverable2.py`. This temporary harness
was removed after verification and is not a repository test. To reproduce its
procedure without touching production data:

1. Create a `tempfile.TemporaryDirectory` and pass its `integration.db` path to
   `create_app({"TESTING": True, "DATABASE_PATH": ...})` in a child Python process.
2. Through Flask's test client, POST `/load-scenario/standard`, then POST
   `/runs/trigger` with `primary_strategy=PREFERENCE` and `max_alternatives=3`.
   Retrieve the full run with `AssignmentEngine.get_run()` using the ID from
   `list_runs()`, verify allocations, and save `dataclasses.asdict(run)` as JSON
   in the temporary directory. Check SQL row counts and the integrity probes
   described above, then exit the client context and process.
3. Start another child Python process with the same database path. Retrieve the
   run and each solution; compare the complete JSON snapshot, recompute metrics
   with `compute_solution_indicators()`, repeat allocation and integrity checks,
   and GET the run and solution pages. Exit this process before cleanup.
4. Remove the temporary directory, including the database, WAL/SHM files, and
   snapshot. No application code, existing tests, or production data were changed.

The full regression command actually executed was:

```sh
PYTHONDONTWRITEBYTECODE=1 pytest -v -p no:cacheprovider --basetemp=/tmp/deliverable2-pytest
```

**612 passed in 6.48s**, with no failures, skips, or expected failures. The
pytest temporary directory and harness were removed afterward. This result
supersedes the older full-suite result below; that result remains as historical
milestone evidence.

## Reproduce the automated checks

From the repository root, activate an environment with `requirements-dev.txt`
installed (which includes the runtime dependencies). The recorded local run used
Python 3.13.7 and `/private/tmp/tech5-solver-venv/bin/python` in place of `python`.

Run the five new integration cases:

```sh
python -m pytest -q -p no:cacheprovider tests/test_team_b_application.py --tb=short
```

Run the relevant Team B suite (one command, portable across shells):

```sh
python -m pytest -q -p no:cacheprovider tests/test_bilp_feasibility.py tests/test_bilp_objectives.py tests/test_bilp_alternatives.py tests/test_solution_metrics.py tests/test_gini.py tests/test_metrics.py tests/test_solvers.py tests/test_contract_and_engine.py tests/test_edge_cases.py tests/test_engine_execution.py tests/test_team_b_application.py --tb=short
```

Run the full suite and quality checks separately so each exit status is visible:

```sh
python -m pytest -q -p no:cacheprovider --tb=short
python -m ruff check .
python -m ruff format --check app tests run.py
```

Recorded results on 2026-10-22: five new integration cases passed; focused suite
**190 passed in 3.16s**; full suite **596 passed, 1 failed in 5.69s**, with no
skips or xfails. Ruff lint passed; formatting reported **47 files already
formatted**. The full pytest command exits unsuccessfully due to the issue below.
That historical run was not green; see the dated Deliverable 2 result above.

## What the integration tests establish

Each test uses a disposable SQLite database through Flask's test client, without
starting a web server. Mock execution and mock comparison raise immediately if
called. The fixture restores the previous global database manager afterward.

The lifecycle runs separately for PREFERENCE, SKILL_FIT, and BALANCED: load the
standard cohort, make one existing requirement mandatory in the temporary
fixture, generate three alternatives, view solutions, generate recommendations,
compare alternatives, lock S02 to P2, and rerun. Independent assertions check
full allocation, capacity bounds, mandatory coverage, locks, and distinctness in
persisted solutions. Historical results must remain unchanged after the rerun.
Required fairness and efficiency indicator keys must be present; recommendations
must reference actual solutions and provide criteria, evidence, and advice.

The infeasible scenario must persist INFEASIBLE with diagnostics and no partial
solutions. The WARNING case uses one genuine CBC solution, then simulates
NOT_SOLVED on the next solve. It checks that the retained solution is persisted
and accessible through the UI. It does not reproduce an actual CBC timeout.

These are automated application checks, not manual browser/visual testing,
performance benchmarking, or proof of all future integration behavior. Tied
optima need not produce identical student allocations on every solver platform.
Alternatives use the selected strategy repeatedly; they are not guaranteed to
be Pareto-optimal or to represent three different strategies in one run.

## Team A follow-up

1. **Existing HTML assertion:**
   `tests/test_visualization_component.py::test_compare_two_alternatives_of_a_run`
   searches response bytes for `Cloud Data Pipeline & Lakehouse`; Jinja correctly
   emits `Cloud Data Pipeline &amp; Lakehouse`. The test remains unchanged and
   unskipped. Team A should compare escaped HTML or parsed visible text on its
   own branch. Milestone 5 also reproduced this assertion problem with the mock
   engine, independently of BILP.
2. **WARNING presentation:** `trigger_run` uses the generic danger flash for
   WARNING, and the run detail template uses a generic status badge. Status and
   retained solutions are accessible. Team A should decide how to distinguish
   an interrupted search with usable solutions from a failed run. This is a
   presentation follow-up, not a request to alter the contract or solver status.

This document is a handoff note; no external message has been sent to Team A.

## Final integration gate

After Team A's PR is reviewed and merged, create a new integration branch from
updated main only with explicit permission. Bring in Team B's changes and repeat
all checks above on the combined code. Coordinate Team A changes with them.
Instructor approval of Team B's model has been received, as reported by the
student. Code review and successful testing of the combined implementation
remain required before merging Team B's implementation into main.
