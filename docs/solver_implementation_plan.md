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
- [ ] Milestone 3: up to K distinct assignments.
- [ ] Milestone 4: metrics and complete domain results.
- [ ] Milestone 5: engine contract and persistence.
- [ ] Milestone 6: automated real-application integration.
- [ ] Instructor approval, review, and final passing checks before merging.

**Next action:** Milestone 3, distinct alternatives, when requested. Confirm the
alternative strategy schedule before implementation. Milestones 1 and 2 are
complete; application execution and aggregate metrics remain unfinished.

## Architecture to preserve

`RunRequest -> AssignmentEngine.validate_inputs -> execute_run ->
AssignmentStrategy.solve -> Assignment objects -> metrics -> Solution ->
AssignmentRun -> RunRepository`.

The strategy returns `(status, assignments, objective_value, diagnostics)`.
The engine owns validation, alternatives, metrics, and persistence; optimization
does not access Flask or the database. Existing retrieval methods already work.
The strategy registry and execution method are unfinished. Individual skill fit
is implemented; aggregate metrics and comparisons are unfinished. UI routes currently catch
`NotImplementedError` and execute a mock; page rendering alone is not solver proof.

## Decisions and open questions

| Item | Evidence / proposed policy | State |
| --- | --- | --- |
| Instructor approval | Specific Team B BILP model | Pending |
| Allocation | Existing interface and validation use exactly one project per student; never fall back to partial allocation | Confirmed 2026-10-22 |
| Capacities | Enforce every positive minimum; zero-minimum projects may stay unused | Confirmed 2026-10-22 |
| Mandatory skills | Team coverage by at least one sufficiently qualified member per skill, required when a project is used | Confirmed 2026-10-22 |
| Locks | APPROVED, MANDATORY, and CONDITIONAL are all active in current validation | Existing policy |
| Solver | PuLP 3.3.0 with its bundled CBC via PULP_CBC_CMD; retains project Python 3.10 compatibility | Pinned; local smoke test passed |
| Objective | P=(M-r+1)/M, unranked=0, cohort-wide M; BALANCED weights 0.5/0.5 | Authorized with Milestone 2 on 2026-10-22 |
| Skill fit | Mean capped proficiency ratios, equal requirement weights; no requirements=1 | Authorized with Milestone 2 on 2026-10-22 |
| Strategies | PREFERENCE, SKILL_FIT, BALANCED are already accepted keys | Existing interface |
| Alternatives | Default K=3; validation accepts integers 1–4; recommend repeated selected objective with no-good cuts | Scheduling policy open |
| Fairness | Treatment of unranked outcomes in rank means, Gini, and comparisons | Open; blocks milestone 4 |
| Soft gaps | Individual unmet requirements versus uncovered team requirements | Open; blocks milestone 4 |
| Omitted catalog | Validation accepts skills=None, but fresh SQLite data may lack referenced skills | Resolve before milestone 5; never invent catalog rows |

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

- [ ] Agree whether to repeat the selected objective or schedule strategies.
- [ ] Implement and validate `excluded_solutions` no-good cuts.
- [ ] Add a small alternative-generation helper with canonical pair sets for
  duplicate checking; stop at K, proven exhaustion, or interruption.
- [ ] Test K=1/3/4, tied objectives, one solution, fewer than K solutions,
  pairwise distinctness, and lock preservation in every result.
- [ ] Document that exhaustion after cuts does not invalidate earlier solutions.

## Milestone 4 — metrics and domain objects

Files: `metrics.py`, `solvers.py`, metric/solver tests, analytical documentation.

- [ ] Complete assignment metadata and construct `Solution` objects.
- [ ] Implement `calculate_gini`, `compute_solution_indicators`, and
  `compare_two_solutions` with existing signatures.
- [ ] Preserve indicator keys consumed by Team A templates/recommendations.
- [ ] Agree and document unranked and soft-gap semantics.
- [ ] Test hand-calculated metrics, deliberately invalid assignments, Gini
  boundaries, comparisons, and domain serialization.
- [ ] Ensure individual skill gaps do not falsely imply failed team coverage.

## Milestone 5 — engine and persistence

Files: `solvers.py`, contract/engine and persistence tests, implementation docs.

- [ ] Register PREFERENCE, SKILL_FIT, BALANCED and implement `execute_run`.
- [ ] Validate direct calls before solving or synchronizing cohort records.
- [ ] Generate UUIDs, configuration, diagnostics, alternatives, and metrics.
- [ ] Reuse repositories with `self.run_repo.db` and existing transactions;
  synchronize entities in foreign-key order without clearing historical data.
- [ ] Resolve omitted skill-catalog behavior for headless callers.
- [ ] Persist and retrieve runs/solutions; preserve convenience API behavior.
- [ ] Test invalid requests without solver invocation, status mapping,
  persistence round trips, comparison, and rollback after write failures.
- [ ] Replace obsolete tests expecting empty registry/NotImplementedError.

Proposed run mapping: structural errors -> INVALID_INPUT; proven infeasibility
before any solution -> INFEASIBLE; requested results or proven exhaustion ->
COMPLETED; timeout/unknown -> WARNING (retain only verified incumbents); solver
failure or invalid extraction -> FAILED. Preserve exact solver termination in
diagnostics. Agree these semantics before integration. Never infer optimality
from a coarse status or confuse timeout with infeasibility.

## Milestone 6 — real application integration

Files: `tests/test_component_integration.py`, Team B test fixtures,
`docs/testing_and_quality.md`, `docs/reproducible_demonstration.md`.

- [ ] Flask-client workflow: seed, run, view, compare, lock, rerun, infeasible run.
- [ ] Disable mock fallback by making mock execution fail in real-engine tests.
- [ ] Verify persisted assignments against all hard constraints.
- [ ] Exercise recommendations and required indicator keys without Team A edits.
- [ ] Report WARNING presentation incompatibilities to Team A if needed.
- [ ] Remove obsolete xfails only when their behavior actually works.
- [ ] Run full pytest suite, Ruff lint, and Ruff format checks; record outcomes.
- [ ] Document reproducible demonstration and known limitations.

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
