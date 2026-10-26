# Team B — Milestone 6 integration verification

**Status:** Integrasjon verifisert mot nåværende applikasjon; endelig integrasjon med Team A gjenstår.

This verifies the application currently on `teamB/build_solver`. It does not
verify unmerged or future Team A changes. No Team A files, shared interfaces,
or production code were modified in this milestone.

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
Do not describe the full suite as green.

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
