# Team B — living solver implementation plan

## Purpose and working rules

This is the implementation checklist, not a frozen design or instructor approval.
Update it when evidence changes the approach. Keep completed work, remaining work,
decisions, and actual verification results visible. Never mark a milestone done
merely because code exists.

- Work on the existing `teamB/build_solver` branch.
- Preserve public signatures, shared domain models, and the component contract.
- Do not modify Team A files or discard existing changes.
- After completing and verifying each milestone, create a local commit on the
  current feature branch. This is standing user authorization (2026-10-22).
  Include the milestone code, focused tests, specification, and updated checklist.
  Inspect the diff and stage explicit paths; do not include unrelated user work.
  Record test results before committing. New regressions must be fixed first;
  documented pre-existing failures do not become hidden or count as a green suite.
- No branch switches, merges, pushes, or pull requests without permission.
- Instructor approval, review, and successful testing remain merge prerequisites.
- Read this plan and `solver_spec.md` before resuming work. Check Git changes.
- Finish and test one milestone before moving on. Update this document with the
  commands, results, limitations, and next action after each implementation step.
- Changes to mathematical policy require an explicit decision, not an assumption
  made to make a failing example solvable.

## Current position

- [x] Inspect contract, domain, validation, solver skeleton, metrics, and tests.
- [x] Create this editable plan.
- [x] Milestone 1: one verified feasible assignment.
- [x] Milestone 2: preference and skill-fit objectives.
- [x] Milestone 3: up to K distinct assignments.
- [x] Milestone 4: metrics and complete domain results.
- [x] Milestone 5: engine contract and persistence — ready for review; Team A UI issue remains.
- [x] Milestone 6: automated integration against the current application.
- [ ] Final integration with Team A after their reviewed changes are available.
- [x] Instructor approval for Team B's BILP model (reported by the student).
- [ ] Code review and final passing checks before merging.

**Status:** Integrasjon verifisert mot nåværende applikasjon; endelig integrasjon med Team A gjenstår.

Milestone 6 is complete for the current checkout, not a certification of Team A's
future changes. The full suite is not green: the known Team A HTML assertion
remains unchanged. Next: review this work and later verify the combined branches
with explicit permission. Instructor approval has been received, as reported
by the student in this session.

## Architecture to preserve

`RunRequest -> AssignmentEngine.validate_inputs -> execute_run ->
AssignmentStrategy.solve -> Assignment objects -> metrics -> Solution ->
AssignmentRun -> RunRepository`.

The strategy returns `(status, assignments, objective_value, diagnostics)`.
The engine owns validation, alternatives, metrics, and persistence; optimization
does not access Flask or the database. Existing retrieval methods already work.
The strategy registry, execution, solution construction, metrics/comparisons,
and atomic persistence are implemented. UI routes retain their existing mock
fallback for `NotImplementedError`; the real engine now executes successfully.
Page rendering alone is not solver proof.

## Decisions and open questions

| Item | Evidence / proposed policy | State |
| --- | --- | --- |
| Instructor approval | Specific Team B BILP model | Received; reported by the student in this session |
| Allocation | Existing interface and validation use exactly one project per student; never fall back to partial allocation | Confirmed 2026-10-22 |
| Capacities | Enforce every positive minimum; zero-minimum projects may stay unused | Confirmed 2026-10-22 |
| Mandatory skills | Team coverage by at least one sufficiently qualified member per skill, required when a project is used | Confirmed 2026-10-22 |
| Locks | APPROVED, MANDATORY, and CONDITIONAL are all active in current validation | Existing policy |
| Solver | PuLP 3.3.0 with its bundled CBC via PULP_CBC_CMD; retains project Python 3.10 compatibility | Pinned; local smoke test passed |
| Objective | P=(M-r+1)/M, unranked=0, cohort-wide M; BALANCED weights 0.5/0.5 | Authorized with Milestone 2 on 2026-10-22 |
| Skill fit | Mean capped proficiency ratios, equal requirement weights; no requirements=1 | Authorized with Milestone 2 on 2026-10-22 |
| Strategies | PREFERENCE, SKILL_FIT, BALANCED are already accepted keys | Existing interface |
| Alternatives | Default K=3, supported 1–4; repeat selected strategy with fixed weights and accumulated cuts | Implemented Milestone 3 |
| Fairness | Same cohort M+1 for unranked numerical ranks; retain None and separate count | Explicitly approved and implemented Milestone 4 |
| Soft gaps | Count non-mandatory gaps per student/project/requirement, canonical individual_unmet_soft_requirements_count | Explicitly approved and implemented Milestone 4 |
| Omitted catalog | skills=None may reference existing database skills; missing rows produce INVALID_INPUT | Implemented in execute_run, no synthetic catalog entries |

The course file referenced as `assignment/projectTech5.tex` is absent from this
checkout. Some architecture documents describe a finished solver that does not
exist yet. Use source and tests to distinguish implementation from intentions.

## Mathematical mapping (baseline confirmed 2026-10-22)

- Binary `x[i,j]` for each student/project pair; use numeric solver variable names
  and original domain IDs as dictionary keys.
- Exact allocation: `sum_j x[i,j] == 1`.
- Capacity: `L[j] <= sum_i x[i,j] <= U[j]`.
- Fixed pair: `x[i,j] == 1`.
- Define qualified students by `get_skill_level(skill_id) >= minimum_level`.
- Mandatory coverage for a used project: `headcount[j] <= U[j] *
  sum(x[i,j] for qualified i)`. This also allows an empty zero-minimum project
  without introducing activation variables. Different members can cover skills.
- Milestone 1 has a constant objective; it establishes feasibility only.
- Milestone 2 objective: maximize `sum((w_p * P[i,j] + w_s * S[i,j]) * x[i,j])`.
  Weights are (1,0), (0,1), or (0.5,0.5); see `solver_spec.md` for scoring.
- Exclude a previous complete allocation A using
  `sum(x[i,j] for (i,j) in A) <= student_count - 1`.
  This simplified cut relies on full allocation.

No-good cuts establish distinctness, not Pareto efficiency. Do not label results
Pareto-optimal without a separate justification.

## Milestone 1 — one feasible assignment

Files: `requirements.txt`, `app/engine/solvers.py`, a focused solver test module,
`docs/solver_spec.md`, and this plan.

- [x] Confirm allocation and project-use policies.
- [x] Pin and smoke-test the dependency on the available environment.
- [x] Implement `AssignmentStrategy.solve` with a constant objective.
- [x] Keep small private functions for model construction, extraction, and
  independent hard-constraint checking where that improves readability.
- [x] Reuse domain validation; distinguish structural errors from proof of
  infeasibility even when both validity flags are false.
- [x] Reject unsupported exclusions explicitly until milestone 3; never ignore
  an argument that affects correctness.
- [x] Check binary values and independently verify returned assignments.
- [x] Return honest termination diagnostics and no invented skill-fit metrics.
- [x] Test a known feasible case, capacity boundaries, complete allocation,
  mandatory proficiency thresholds, coverage split across members, fixed locks,
  unused optional projects, invalid inputs, and proven infeasibility.
- [x] Test joint infeasibility missed by necessary prechecks: two required
  projects competing for the same uniquely qualified student.
- [x] Test solver failure, unverified values, and timeout/status interpretation
  using controlled solver results as well as real CBC solves.

Use a test-only constant-utility strategy. Do not register production objective
strategies or implement `execute_run` yet. No Team A or metrics dependency.
Completion gate: focused tests and lint pass, actual results recorded below.

## Milestone 2 — preference and skill objectives

Files: `solvers.py`, `metrics.py`, `tests/test_bilp_objectives.py`,
`tests/test_bilp_feasibility.py`, `tests/test_metrics.py`, `solver_spec.md`,
`analytical_formulation.md`, and this plan.

- [x] Agree scoring formulas, normalization, weights, and unranked policy.
- [x] Implement the three small concrete strategies' utility methods.
- [x] Implement `calculate_assignment_skill_fit` once and reuse it.
- [x] Add the weighted objective to the shared solve implementation.
- [x] Test known optimal values, unranked/no preferences, unequal list lengths,
  missing skills, overqualification, and projects without requirements.
- [x] Compare tiny examples against exhaustive enumeration in tests.
- [x] Record formulas and passing checks. No Team A changes.

## Milestone 3 — distinct alternatives

Files: `solvers.py`, solver tests, `solver_spec.md`, this plan.

- [x] Agree whether to repeat the selected objective or schedule strategies.
- [x] Implement and validate `excluded_solutions` no-good cuts.
- [x] Add a small alternative-generation helper with canonical pair sets for
  duplicate checking; stop at K, proven exhaustion, or interruption.
- [x] Test K=1/3/4, tied objectives, one solution, fewer than K solutions,
  pairwise distinctness, and lock preservation in every result.
- [x] Document that exhaustion after cuts does not invalidate earlier solutions.

## Milestone 4 — metrics and domain objects

Files: `metrics.py`, `solvers.py`, metric/solver tests, analytical documentation.

- [x] Complete assignment metadata and construct `Solution` objects.
- [x] Implement `calculate_gini`, `compute_solution_indicators`, and
  `compare_two_solutions` with existing signatures.
- [x] Preserve indicator keys consumed by Team A templates/recommendations.
- [x] Agree and document unranked and soft-gap semantics.
- [x] Test hand-calculated metrics, deliberately invalid assignments, Gini
  boundaries, comparisons, and domain serialization.
- [x] Ensure individual skill gaps do not falsely imply failed team coverage.

## Milestone 5 — engine and persistence

Files: `solvers.py`, contract/engine and persistence tests, implementation docs.

- [x] Register PREFERENCE, SKILL_FIT, BALANCED and implement `execute_run`.
- [x] Validate direct calls before solving or synchronizing cohort records.
- [x] Generate UUIDs, configuration, diagnostics, alternatives, and metrics.
- [x] Reuse repositories with `self.run_repo.db` and existing transactions;
  synchronize entities in foreign-key order without clearing historical data.
- [x] Resolve omitted skill-catalog behavior for headless callers.
- [x] Persist and retrieve runs/solutions; preserve convenience API behavior.
- [x] Test invalid requests without solver invocation, status mapping,
  persistence round trips, comparison, and rollback after write failures.
- [x] Replace obsolete tests expecting empty registry/NotImplementedError.

Milestone 5 run mapping: structural errors -> INVALID_INPUT; proven infeasibility
before any solution -> INFEASIBLE; requested results or proven exhaustion ->
COMPLETED; timeout/unknown -> WARNING (retain only verified incumbents); solver
failure or invalid extraction -> FAILED. Preserve exact solver termination in
diagnostics. Never infer optimality
from a coarse status or confuse timeout with infeasibility.

## Milestone 6 — integration against the current application

Files: `tests/test_team_b_application.py`, this plan, and
`docs/team_b_integration_verification.md`. Existing Team A tests and shared
application documentation remain unchanged.

- [x] Flask-client workflow: seed, run, view, compare, lock, rerun, infeasible run.
- [x] Fail tests if mock execution or comparison fallback is used.
- [x] Independently verify persisted allocations, capacities, mandatory skills,
  fixed assignments, distinctness, and unchanged historical results.
- [x] Exercise all three strategies, recommendations, and required indicator keys.
- [x] Verify WARNING retains a real solution; document UI presentation for Team A.
- [x] Check existing xfails: none remain; no skips or xfails added or removed here.
- [x] Run full pytest, Ruff lint, and formatting checks; record actual results.
- [x] Document reproducible automated verification and limitations.

### Later final integration (not performed by this milestone)

After Team A's PR is reviewed and merged, obtain explicit permission to create
an integration branch from updated main and bring in Team B's changes. Rerun
integration tests, full pytest, and Ruff against the combined code. Coordinate
any Team A edits with their owners. Merge only after instructor approval,
review, and passing checks. This milestone does not authorize a push or merge.

## Verification and change log

### 2026-10-22 — plan created and milestone 1 started

- Repository starts on `teamB/build_solver`; existing untracked `AGENTS.md` and
  `solver_spec.md` preserved.
- Historical baseline from `testing_and_quality.md`: 4 failed, 440 passed,
  12 xfailed on October 21. This is not a newly executed baseline.
- Available Python: 3.13.7. No local pytest, PuLP, or Ruff installation found.
- Temporary environment: `/private/tmp/tech5-solver-venv`.
- Dependency installation succeeded after network approval. `requirements.txt`
  now pins PuLP 3.3.0. Its package metadata requires Python >=3.9; actual execution
  was tested only on this machine's Python 3.13.7, not all team platforms.
- CBC smoke test: one binary variable, maximize x with x <= 1; solver status and
  solution status both optimal, x=1.0. Both statuses must be inspected in PuLP 3.x
  because an incumbent after interruption does not establish optimality.
- Newly executed baseline:
  `/private/tmp/tech5-solver-venv/bin/python -m pytest -q -p no:cacheprovider`
  -> **4 failed, 440 passed, 12 xfailed in 2.40s**. All four failures are the
  existing capacity tests reaching unimplemented `execute_run`; no tests changed.
- Model-policy confirmation pending; no mathematical policy silently finalized.

Dependency references:
- [PuLP 3.3.0 release](https://pypi.org/project/PuLP/3.3.0/)
- [Official migration guide](https://coin-or.github.io/pulp/guides/how_to_migrate_to_v4.html)
  explains the Python 3.12 minimum and changed status API in PuLP 4. Do not mix
  PuLP 4 examples with the pinned 3.3.0 implementation.

For each later entry record: what changed, why, exact test/check results, remaining
risks, any revised decision, and the next unchecked action.

### 2026-10-22 — confirmed policy and pre-implementation baseline

- User confirmed exact allocation, unconditional capacity bounds, and mandatory
  team coverage only for used projects. No silent partial allocation.
- Conditional coverage uses the equivalent capacity-times-qualified-count
  inequality; no extra activation variable is needed.
- Before editing solver code, ran `python -m pytest -q -p no:cacheprovider
  tests/test_solvers.py --tb=short` in the temporary environment:
  **4 failed, 3 passed, 1 xfailed**. The four capacity cases (zero-minimum,
  at-minimum, at-maximum, equal-bounds) all fail at test line 67 because
  `AssignmentEngine.execute_run` raises `NotImplementedError`. Assignment
  assertions are never reached. These remain expected baseline failures until
  milestone 5; their tests will not be weakened or hidden.

### 2026-10-22 — Milestone 1 completed

- Implemented the shared feasibility-only `AssignmentStrategy.solve`, model
  construction, binary extraction, and independent assignment verification in
  `app/engine/solvers.py`. No contract/domain/Team A files changed.
- Added `tests/test_bilp_feasibility.py`: 33 cases cover actual CBC solves,
  capacity boundaries, fixed statuses, skill levels, split team coverage,
  optional unused projects, joint infeasibility, positive minima despite locks,
  input rejection, safe variable names, input immutability, and simulated
  interruption/error/invalid output handling.
- Tests deliberately raise if the utility method is invoked. No objective
  scoring or alternative generation was introduced. No existing tests or xfails
  were changed. `execute_run` and production strategy registration remain TODO.
- Commands use `/private/tmp/tech5-solver-venv/bin/python`:
  - `-m pytest -q -p no:cacheprovider --tb=short`:
    **473 passed, 4 failed, 12 xfailed in 2.10s**.
  - All four failures are the exact pre-existing engine capacity cases documented
    above. Their exception moved to line 362 as solver code was added; its cause
    is unchanged. No new regressions observed.
- Status limitation: CBC/PuLP's coarse stopped/unknown result is NOT_SOLVED,
  never INFEASIBLE. Do not claim a specific timeout cause without log evidence.
  Reported incumbents are independently verified and warned when not optimal.
- Skill metrics remain uncomputed and are labeled as such in diagnostics.
- Instructor approval and platform verification beyond local Python 3.13/macOS
  remain outstanding. No branches switched, commits, pushes, or merges made.

- Final focused check: `-m pytest -q -p no:cacheprovider
  tests/test_bilp_feasibility.py` -> **33 passed in 0.33s**.
- Final quality checks: `-m ruff check app tests run.py` passed;
  `-m ruff format --check app tests run.py` passed (41 files);
  `git diff --check` passed.

### 2026-10-22 — milestone commit workflow

- User authorized a local commit after every completed, verified milestone.
- Capture the already verified Milestone 1 as its own commit before Milestone 2,
  so feasibility and scoring can be reviewed independently.
- Existing untracked `docs/AGENTS.md` is user-provided guidance and is not staged
  as part of the implementation. No push is authorized.

### 2026-10-22 — Milestone 2 implementation

- Milestone 1 committed as `9bcf5a0` before starting scoring changes.
- User authorized Milestone 2 following the explicit scoring proposal; formulas
  and rationale are now recorded in solver_spec.md.
- Added three concrete strategies, a shared cohort-normalized preference helper,
  and the weighted maximization objective. Hard constraints remain unchanged.
- Implemented individual skill fit once in metrics.py and populate assignment
  fit/gaps. Aggregate metrics remain unimplemented and labeled accordingly.
- Preserve FEASIBLE success status; objective values are real verified scores,
  and optimality_proven requires both CBC/PuLP status fields to prove optimality.
- Updated the original zero-utility test strategy for the new shared solve flow;
  no hard-constraint assertions removed. Removed only the skill-fit xfail now
  that its original assertion passes.
- Added scoring boundaries and independent exhaustive enumeration (27 possible
  allocations each) across all strategies, locks, and mandatory coverage. Tests
  compare objective values rather than assuming a tie order.

- Verification using `/private/tmp/tech5-solver-venv/bin/python`:
  - `-m pytest -q -p no:cacheprovider tests/test_bilp_objectives.py
    tests/test_bilp_feasibility.py tests/test_metrics.py`:
    **60 passed, 3 xfailed** (26 new objective cases, 33 feasibility cases,
    and the original now-passing skill-fit case).
  - `-m pytest -q -p no:cacheprovider --tb=short`:
    **500 passed, 4 failed, 11 xfailed in 2.37s**. The four failures remain
    `test_real_engine_accepts_capacity_boundaries` (zero-minimum, at-minimum,
    at-maximum, equal-bounds), all from unimplemented execute_run. No new failures.
- The only removed xfail is calculate_assignment_skill_fit. The remaining
  unfinished features are not hidden or marked implemented.
- Milestone 2 includes only objectives and individual assignment skill metadata;
  no alternatives, aggregate indicators, engine registration, or UI changes.
- Commit this milestone locally after final lint/format/diff checks; no push.

- Final quality checks passed: `ruff check app tests run.py`,
  `ruff format --check app tests run.py` (42 files), and `git diff --check`.

### 2026-10-22 — Milestone 3

- Continued the planned simplest schedule: repeatedly optimize the selected
  strategy, without changing weights. No alternative-objective policy added.
- Implemented validated, deduplicated no-good cuts in the existing solve API;
  independently reject excluded results during extraction.
- Added private `_generate_alternatives`, returning existing assignment tuples
  and per-attempt diagnostics without changing the public contract. Stop at K,
  proven exhaustion, failure, duplicate, or a verified nonoptimal incumbent.
- Preserve earlier feasible solutions on every later stopping condition. Never
  label exhaustion under cuts as infeasibility of earlier assignments.
- Replaced the old exclusion-not-implemented test with an actual exhaustion
  assertion. Added `tests/test_bilp_alternatives.py` covering all strategies,
  K=1/3/4, default K, tied scores, fewer alternatives, locks/skills, invalid cuts,
  duplicate cuts, objective ordering, and interrupted searches.
- Limits remain per solve (15 seconds), not per alternative search. No extra
  solve after K; no Pareto or exhaustive-enumeration claim on reaching K.
- No engine integration, aggregate metrics, UI edits, or pushes in this milestone.

- Verification with `/private/tmp/tech5-solver-venv/bin/python`:
  - `-m pytest -q -p no:cacheprovider tests/test_bilp_alternatives.py
    tests/test_bilp_feasibility.py tests/test_bilp_objectives.py`:
    **88 passed** (29 new alternative cases).
  - `-m pytest -q -p no:cacheprovider --tb=short`:
    **529 passed, 4 failed, 11 xfailed in 3.49s**. All four failures remain the
    original execute_run capacity-boundary cases; no new failures or xfails.
  - Ruff lint passed; Ruff formatting passed across 43 files; git diff check passed.
- Reviewed implementation and test diffs. Commit Milestone 3 locally with its
  documentation and tests; preserve untracked user guidance `docs/AGENTS.md`.

### 2026-10-22 — Milestone 4 started (not complete)

- Inspected existing metric tests, mock payloads, domain models, recommendation
  consumers, and templates. The mock uses synthetic fairness values and cannot
  establish a real policy for unranked ranks or soft-gap counts.
- Implemented calculate_gini independently of those policy decisions. Empty and
  all-zero inputs return 0; negative/nonfinite values raise ValueError. Sorting
  uses the standard weighted-sum formula; scaling prevents large-value overflow.
- Added tests/test_gini.py (13 cases) and removed only the now-obsolete Gini xfail.
- Focused verification: `python -m pytest -q -p no:cacheprovider
  tests/test_gini.py tests/test_metrics.py` -> **15 passed, 2 xfailed**.
  Ruff checks on these changed files passed.
- Awaiting user confirmation of proposed metric policy: use cohort M+1 for
  unranked numerical rank statistics (retain None in assignment metadata), and
  count soft gaps per student/project/requirement. These are proposals, not yet
  implemented or treated as approved.
- No milestone completion commit until the remaining implementation and
  verification are finished. No contract or Team A changes.

- Full suite after Gini: **543 passed, 4 baseline failures, 10 xfailed in
  2.98s** (`python -m pytest -q -p no:cacheprovider --tb=short`). All four
  failures still come from unimplemented execute_run. `git diff --check` passed.

### 2026-10-22 — Milestone 4 completed

- User approved cohort-wide M+1 numerical penalties, retaining actual None ranks,
  including M=0 when all preference lists are empty. Approved individual soft-gap
  counts excluding mandatory skills, with a descriptive canonical metric name.
- Implemented feasibility/efficiency/fairness/capacity indicators and comparisons
  in metrics.py. Kept existing soft-count key as an explicitly documented alias;
  solution warnings explain that it is not team-level uncovered requirements.
- Added private `_build_solution` for verified domain conversion, fresh metadata,
  real indicators, copied assignments, UUIDs, and preserved warnings/diagnostics.
  No execute_run implementation or persistence work included.
- Added tests/test_solution_metrics.py for mixed ranks, shared penalties across
  real alternatives, individual-vs-team coverage, invalid assignments, comparison
  directions/deltas, legacy missing penalties, and JSON/domain round trips.
- Removed only implemented metric xfails; updated the contract test that formerly
  expected comparison to raise NotImplementedError to verify real delegation.
- Comparisons reject different student sets or conflicting recorded penalties.
  Legacy missing penalties are disclosed; no fabricated rank 99 is introduced.
  UI handling of incompatible comparisons remains an integration consideration.
- No shared models, contract, Team A, or unrelated files modified.

- Final verification using `/private/tmp/tech5-solver-venv/bin/python`:
  - `-m pytest -q -p no:cacheprovider tests/test_solution_metrics.py
    tests/test_metrics.py tests/test_gini.py tests/test_contract_and_engine.py
    --tb=short` -> **59 passed in 0.39s**.
  - `-m pytest -q -p no:cacheprovider --tb=short` -> **565 passed, 4 failed,
    8 xfailed in 3.39s**. Failures remain the four original capacity tests that
    reach unimplemented execute_run. No new regressions observed.
  - `ruff check app tests run.py`, `ruff format --check app tests run.py`
    (45 files), and `git diff --check` passed.
- Reported these results to the user before committing, as requested. Create
  the local milestone commit under the standing workflow; do not push.

### 2026-10-22 — Milestone 5 integration (ready for review)

- Registered all strategies and implemented execute_run, metadata, validation,
  search status mapping, real domain results, and atomic persistence using the
  injected repository database. No Flask dependencies added to engine logic.
- Omitted catalogs resolve references only against existing database rows;
  missing referenced IDs produce INVALID_INPUT, never invented skills.
- Existing rejected requests persist only diagnostics. Successful or partially
  successful searches synchronize supplied entities and save the full run in
  one transaction; persistence errors propagate and roll back.
- Added tests/test_engine_execution.py covering all strategies, round trips,
  input immutability, rejected requests, catalog policies, warning/failure with
  and without incumbents, rollback, and fixed-lock reruns preserving history.
- Replaced obsolete skeleton assertions in solver/contract tests. Removed seven
  obsolete solver xfails in test_edge_cases.py and isolated their SQLite fixture;
  they previously inherited another test's simulated-failure database trigger.
- The original four capacity-boundary failures now pass. Focused execution and
  edge tests: **31 passed**. Full run: **591 passed, 1 failed**, no xfails.
- Final focused Team B verification: **185 passed in 3.15s** using
  `/private/tmp/tech5-solver-venv/bin/python -m pytest -q -p no:cacheprovider`
  with `tests/test_bilp_feasibility.py`, `tests/test_bilp_objectives.py`,
  `tests/test_bilp_alternatives.py`, `tests/test_solution_metrics.py`,
  `tests/test_gini.py`, `tests/test_metrics.py`, `tests/test_solvers.py`,
  `tests/test_contract_and_engine.py`, `tests/test_edge_cases.py`, and
  `tests/test_engine_execution.py`, plus `--tb=short`.
- Full suite, with no test excluded, skipped, or marked xfail:
  `/private/tmp/tech5-solver-venv/bin/python -m pytest -q -p no:cacheprovider --tb=short`
  -> **591 passed, 1 failed in 4.51s**.
- `/private/tmp/tech5-solver-venv/bin/python -m ruff check .` -> all checks passed.
  Ruff format check on `app/engine` and the four changed test modules ->
  **8 files already formatted**. `git diff --check` passed.
- Reviewed engine implementation, new execution tests, updated Team B skeleton
  tests, and solver documentation. No Team A application files or tests, shared
  contract, domain models, or persistence implementation were modified.
  Untracked user-owned `docs/AGENTS.md` remains excluded from the commit.
- User explicitly accepted review readiness with this sole unrelated UI failure.
  Local milestone commit is authorized by the standing workflow; no push or merge.
  Full-suite success remains an outstanding merge prerequisite.

#### Team A handoff — HTML assertion (open, owner: Team A)

- Location: `tests/test_visualization_component.py:881`,
  `test_compare_two_alternatives_of_a_run`. The file remains unchanged.
- Reproduce with the full-suite command above or target that single test.
- Actual: HTTP 200; Jinja correctly renders
  `Cloud Data Pipeline &amp; Lakehouse`. The test searches raw response bytes for
  `Cloud Data Pipeline & Lakehouse`, so its unescaped-string assertion fails.
- A separate temporary-database reproduction replaced AssignmentEngine with
  MockAssignmentEngine for both execution and comparison, then gave the first
  changed project the same ampersand-containing title. The escaped title was
  present and the raw title absent. Thus the assertion problem reproduces
  independently of Team B's BILP implementation. Real allocations exposed a
  latent test assumption; this is not a claim that the test failed on the old
  mock-selected data before Milestone 5.
- Team A should correct the assertion on its own branch by checking HTML-escaped
  text or parsed visible text, keeping template autoescaping enabled. No fix or
  skip is applied by Team B. This note is the review handoff; no external message
  has been sent to Team A.

### 2026-10-22 — Milestone 6 completed against current application

- Added five Team B test cases: lifecycle for each of three strategies,
  infeasible application run, and WARNING after one real CBC solution followed
  by a simulated interrupted solve. Tests use temporary SQLite databases and
  forbid mock execution/comparison fallback. No production code changed.
- Last executed focused Team B suite: **190 passed in 3.16s**.
- Last executed full suite: **596 passed, 1 failed in 5.69s**, no skips or xfails.
  Sole failure remains the Team A raw `&` versus escaped `&amp;` assertion at
  `tests/test_visualization_component.py:881`; see the Milestone 5 handoff.
- Ruff check: **all checks passed**. Ruff format check: **47 files already
  formatted**. Commands, coverage, and limitations are in the dedicated
  [Team B verification guide](team_b_integration_verification.md).
- Team A follow-up: WARNING renders and retains accessible solutions, but the
  trigger route uses a danger flash and the detail page a generic status badge.
  Team A should review presentation; this is not a solver failure or evidence
  that their application needs rebuilding. No external message was sent.
- Diff reviewed: only the new Team B test file, this plan, and the new Team B
  guide are included. User-owned untracked docs/AGENTS.md remains unstaged.
- Local milestone commit authorized. No branch switch, push, or merge.

### Instructor approval update

The student reports that instructor approval for Team B's BILP model has been
received. Current status and specification now reflect this; earlier milestone
logs record the state at that time. This does not authorize a branch switch,
push, or merge. Code review, resolution of the known UI assertion, and final
integration testing with Team A remain outstanding.
