# Team B – Assignment Solver Specification

## Status
Proposed approach: Binary Integer Linear Programming (BILP).

Instructor approval: Pending.

This document defines the proposed model for implementation planning and preliminary development. Do not treat unresolved assumptions as approved requirements.

## Existing Architecture

The solver is part of Team B's Assignment Engine.

Inputs originate from `RunRequest` and the shared domain models.

Results must be compatible with the existing `AssignmentEngineContract`, `AssignmentRun`, `Solution`, and `Assignment` classes.

Do not modify these interfaces without agreement between Team A and Team B.

## Decision Variables

For each student i and project j:

x[i,j] = 1 if student i is assigned to project j, otherwise 0.

All x[i,j] are binary.

## Hard Constraints

### Student Allocation
Each student must be assigned to exactly one project: sum_j x[i,j] = 1.
If no full allocation satisfies every hard constraint, report infeasibility.
Never silently return a partial assignment. A partial-allocation mode requires
separate explicit agreement. This preserves the existing application policy.

### Project Capacity
For each project j:

L[j] <= sum(x[i,j] for i in students) <= U[j]

Enforce these bounds for every project. Positive minima require staffing; a
project with minimum 0 may remain unused. A project cannot be closed to evade
a positive minimum. This matches existing validation and capacity tests.

### Mandatory Skill Requirements
For each mandatory skill k required by a project j that receives students,
at least one assigned student must possess skill k at the required proficiency
level or higher. An unused project with minimum 0 needs no mandatory coverage.

Different mandatory requirements may be satisfied by different students.

Let n[j] = sum_i x[i,j], and Q[j,k] contain the qualified students. Implement
conditional coverage as n[j] <= U[j] * sum(x[i,j] for i in Q[j,k]). If n[j] > 0,
the integer qualified-member count must be at least 1; if n[j] = 0 the constraint
is satisfied. This avoids an unnecessary activation variable while expressing
the confirmed policy exactly. Qualification uses >= minimum_level.

These baseline decisions were confirmed by the user on 2026-10-22 for preliminary
feature-branch development. Instructor approval remains pending.

### Fixed Assignments
Administrative fixed assignments must be preserved throughout optimization and when generating alternative solutions.

## Optimization Objective

Proposed objective:

Maximize the weighted sum of preference satisfaction and student-project skill compatibility.

The proposed mathematical structure is:

maximize sum((w_p * P[i,j] + w_s * S[i,j]) * x[i,j])

### Milestone 2 scoring baseline (2026-10-22)

The user authorized Milestone 2 after the following scoring proposal. These are
Team B's preliminary implementation rules; instructor approval remains pending.

Let M be the maximum number of ranked preferences submitted by any student in
this run. For a ranked project with rank r, P[i,j] = (M - r + 1) / M. Unranked
projects score 0. When M=0, all preference scores are 0 (no division). Validation
already requires contiguous positive ranks. Use one cohort-wide M so the same
rank gets the same utility even when students submit different list lengths.
For M=3, ranks 1/2/3 score 1, 2/3, 1/3; unranked projects score 0.

S[i,j] is the arithmetic mean over all project requirements of
min(student_level / required_level, 1). Missing skills have level 0. Mandatory
and optional requirements have equal scoring weight. Projects without any
requirements score 1, preserving existing behavior. The unmet list contains
skills whose levels fall below the requirement, in requirement order.

| Strategy key | Preference weight | Skill-fit weight |
| --- | --- | --- |
| PREFERENCE | 1 | 0 |
| SKILL_FIT | 0 | 1 |
| BALANCED | 0.5 | 0.5 |

Maximize the sum of pair utilities across assignments, not their average. Since
allocation is exact, dividing by cohort size would not change the optimum.
Pair utilities range from 0 to 1 and a run's objective from 0 to cohort size.
All hard constraints are unchanged; a high score never excuses a violation.
An individual may lack mandatory skills when other assigned members cover them.

Limitations: equal normalized weights are a transparent baseline, not evidence
of an ideal trade-off. Changing M changes rank spacing. A no-requirement project
scores full skill fit and may be favored by skill-oriented objectives. Rank
inequality is not optimized. Equal-score solutions have no guaranteed tie order;
no tie-breaking objective or multiple-alternative logic is implemented.

## Alternative Solutions

Milestone 3 repeats the selected strategy with unchanged weights, using the
simplest schedule proposed in the implementation plan. Default K=3; existing
validation permits integer K from 1 to 4. Strategies are not rotated.

Two allocations are distinct only if at least one student's project differs.
For each previous complete allocation A, add the no-good cut
`sum(x[i,j] for (i,j) in A) <= number_of_students - 1`. Accumulate all cuts.
This works because each student is allocated exactly once. Locks and every other
hard constraint remain active in every solve. Equal scores can produce distinct
assignments; arbitrary tie ordering is allowed.

Exclusions must be lists of complete allocations, each containing one tuple of
known student/project string IDs per student. Malformed/incomplete exclusions
return INVALID_INPUT before solving. Repeated exclusions are canonicalized and
added only once. Exclusions need not be feasible under the current constraints;
excluding an infeasible complete assignment cannot remove a feasible assignment.
Inputs are not modified. Extraction also rejects a result matching a cut.

The private `_generate_alternatives` helper returns a list of existing
assignment/score/diagnostic tuples and search diagnostics, ready for later engine
integration. It does not create or persist AssignmentRun/Solution objects yet.
It stops at:

| Stop reason | Interpretation |
| --- | --- |
| K_REACHED | K verified distinct solutions obtained; exhaustion is not claimed. |
| EXHAUSTED | A later solve proved no further allocations remain; earlier results remain valid. |
| INFEASIBLE | No solution exists before any alternative was accepted. |
| NON_OPTIMAL_INCUMBENT | Keep the verified incumbent, then stop; best-K ordering is not established. |
| NOT_SOLVED / FAILED / INVALID_INPUT | Retain earlier results and report the actual stopping condition. |
| DUPLICATE | Defensive check rejected a repeated result; no padding or retry loop. |

Each attempt preserves its status and diagnostics. Each solve uses the existing
15-second limit, so up to K solves may consume approximately K times that limit,
plus setup time. This is not a total-run time budget. There is no extra solve
after reaching K. Only if every accepted solve proves optimality can results be
called successive best assignments under the same objective and exclusions.
Distinctness does not establish Pareto efficiency.

## Solver Results

Use the existing domain objects and public interfaces.

Preserve:
- Assignment decisions
- Objective value where available
- Solver status
- Useful diagnostics
- Information required by metrics.py
- Distinct alternative solutions

Never confuse solver timeout or unknown status with proven infeasibility.

## Testing Requirements

Test at least:
1. A small feasible cohort with a known assignment.
2. Student allocation constraints.
3. Minimum and maximum project capacities.
4. Mandatory skill qualification.
5. Administrative fixed assignments.
6. Infeasible cohorts.
7. Alternative-solution distinctness.
8. Compatibility with existing domain objects and engine interfaces.

All claimed successful solutions must satisfy the hard constraints.

## Simplicity

Prefer one clear solver implementation using the approved solver library.

Avoid custom optimization frameworks, unnecessary inheritance, and duplicated domain classes.

Explain any non-obvious solver-specific API calls.

## Documentation

Document the mathematical assumptions, scoring decisions, solver library, alternative generation method, and known limitations.

Keep this specification synchronized with implemented behavior.

## Milestone 1 implementation (historical snapshot, 2026-10-22)

`AssignmentStrategy.solve` now solves the confirmed hard constraints with PuLP
3.3.0 and its bundled CBC. It uses the existing 15-second configuration limit.
The internal objective is constant zero; the public objective value is None.
No preference/skill objective, alternatives, metrics, or engine orchestration
has been implemented. The abstract utility method is deliberately not called.
A test-only strategy exercises the shared solver without registering a new
production strategy. Nonempty excluded_solutions raises NotImplementedError
rather than silently ignoring exclusions.

The solver validates inputs, constructs binary variables, solves, checks all
variable values for finiteness and binary tolerance (1e-6), and independently
verifies every hard constraint on the extracted Assignment objects. Student and
project IDs are not used in solver variable names, avoiding name collisions.
Preference ranks and fixed flags are populated; skill_fit_score and
unmet_requirements retain domain defaults and are not calculated metrics.
Diagnostics explicitly state metrics_computed=False.

Internal tuple statuses (not new RunStatus values):

| Status | Meaning |
| --- | --- |
| FEASIBLE | A full assignment was independently verified. No scoring optimality claim. |
| INVALID_INPUT | Structural validation failed; CBC was not called. |
| INFEASIBLE | Validation or CBC proved the hard constraints impossible. |
| NOT_SOLVED | No solver-reported incumbent; timeout/unknown is not infeasibility. |
| FAILED | Solver execution failed, unexpected unbounded status, or output verification failed. |

Both PuLP problem and solution statuses are retained. PuLP 3.3.0 can label a
stopped solve Optimal while its solution status is only IntegerFeasible; such an
incumbent is returned only after verification and carries a warning. The wrapper
does not infer a specific timeout cause from these coarse statuses. Exact
interruption diagnosis would require additional CBC log handling and is not
implemented. Solver timing and decision-variable/constraint counts are recorded;
variable count excludes PuLP's internal constant-objective dummy variable.

Instructor approval remains pending. Application execution still reaches the
existing engine skeleton/mock fallback; this milestone proves the standalone
hard-constraint solver, not production application integration.


## Milestone 2 implementation (2026-10-22)

Concrete PreferenceOrientedSolver, SkillFitOrientedSolver, and
BalancedTradeoffSolver now supply utilities to the same hard-constraint model.
The solver maximizes their weighted sum and returns the score recomputed from
verified assignment choices. A zero score is valid; failure results still return
None. The tuple success status remains FEASIBLE. Only diagnostics with
optimality_proven=True establish optimality, requiring both PuLP status fields
to be optimal. A verified interrupted incumbent retains its score and a warning.

Assignments now carry calculated skill_fit_score and unmet_requirements using
the shared metrics function. assignment_skill_fit_computed=True marks this;
metrics_computed=False still means aggregate solution indicators are unfinished.
The strategy key and cohort max_preferences are recorded in diagnostics.

Only the skill-fit function in metrics.py is completed. Gini, solution indicators,
comparisons, strategy registration in AssignmentEngine, execute_run, and distinct
alternatives remain future milestones. The original Milestone 1 regression suite
uses a test-only zero-utility strategy; its expected successful score is now 0.0.

## Milestone 3 implementation (2026-10-22)

Exclusions and the private alternative loop are now implemented. Earlier
milestone descriptions are historical snapshots; nonempty exclusions no longer
raise NotImplementedError. Aggregate metrics, engine registration, execute_run,
and application integration are still future work. Instructor approval remains
pending. No contract, domain, UI, or persistence interface changed.


## Milestone 4 — indicators and domain solutions

The user confirmed the following definitions for implementation. These analytical
rules do not change the objective, allocation decisions, or hard constraints.

### Rank statistics and unranked assignments

`Assignment.preference_rank` stays None when the assigned project is unranked.
Compute M from the maximum preference-list length across the **entire input
cohort**, not from selected assignments. Every solution in a run receives that
same cohort. When all preference lists are empty, M=0.

For numerical statistics only, substitute M+1 for None. This is an **analytical
penalty, not an actual preference rank**. Use these numerical values in mean
rank, worst rank, population variance (divide by n), and rank Gini. Actual rank
histograms contain only `rank_1`, `rank_2`, etc.; unranked_count/unranked_pct report
unranked assignments separately. The fairness dictionary records max_preferences,
unranked_penalty, and rank_statistics_scope, so comparisons can check the scale.
For [rank 1, unranked] and M=3, the numerical values are [1,4]: mean 2.5, worst 4,
variance 2.25, Gini 0.3, and unranked_count=1. Neither assignment is relabeled 4.

For an empty assignment list, numerical summaries return zero, but a missing or
empty cohort/assignment is not a feasible solution. Gini returns zero for empty
or all-zero input and rejects negative/nonfinite values. For n sorted values,
G = sum((2*i-n-1)*x[i]) / (n*sum(x)), with one-based i. Scaling by the largest
value prevents overflow. Equal penalties can yield Gini=0 even when everyone is
unranked: equality is not evidence of satisfaction. Inspect unranked_count too.

### Individual soft-requirement gaps

The canonical metric is
`efficiency.individual_unmet_soft_requirements_count`:
count one for each assigned student–project–requirement combination where the
requirement is non-mandatory and the student's level is below the required level.
Do not count mandatory requirements. Missing skills have level zero.

This measures **individual compatibility**, not uncovered team requirements.
Example: a team of two has an optional SQL requirement; one member qualifies and
the other does not. The team covers SQL but the individual gap count is 1.
A mandatory skill missing from one member is not included in the soft count,
and does not violate feasibility if another assigned member covers it.
`Assignment.unmet_requirements` still lists all individual gaps, including
mandatory ones, as defined by the existing domain object.

For compatibility with existing templates/recommendations,
`unmet_soft_requirements_count` is retained as an alias of this individual count,
not a second team metric. `soft_requirement_count_scope` explicitly records
`individual_student_project_requirement`. Built solutions with gaps carry a
warning explaining this meaning. No Team A labels or recommendation code changed;
those existing labels remain generic and must be interpreted with this warning.

### Feasibility, efficiency, and capacity

Indicators independently check known references, exactly one row per student,
all capacity bounds, mandatory coverage on used projects, and fixed assignments.
They list violations instead of claiming invalid output is feasible. Unknown
references and repeated-student rows are excluded from numerical summaries;
remaining summaries on infeasible output are diagnostic, not valid outcomes.
Inputs are expected to have passed cohort validation.

Mean skill fit and total skill fit aggregate Assignment.skill_fit_score. The
solution builder refreshes rank/fit/gap/fixed metadata from current domain inputs
before calculation. Direct metric callers must supply accurate metadata (the
existing tests intentionally pass explicit scores). No input objects are mutated.
Capacity utilization is assigned count / maximum capacity * 100, both per project
and overall; zero denominator returns zero. Unranked percentage uses summarized
assignment count; valid solutions assign the whole cohort.

### Solution construction and comparison

`_build_solution` converts a verified assignment/score/diagnostic result into an
existing Solution with a UUID, supplied parent run ID, alternative number,
strategy, indicators, warnings, and metrics_computed=True. It checks feasibility,
copies assignments, and never persists or runs the Flask application. The same
complete cohort must be supplied for each alternative. Engine orchestration is
still Milestone 5.

Comparisons report B minus A for mean fit, mean penalized rank, unranked count,
and Gini when both solutions report it. Display deltas are rounded to 10 decimal
places to suppress floating-point noise. Changed rows preserve actual ranks and
use the common recorded penalty for numerical rank_delta. Ranked beats unranked;
two unranked outcomes have SAME direction. Summaries describe calculated changes
without claiming that lower inequality implies universally better assignments.

Comparisons require identical uniquely assigned student sets. Conflicting
recorded penalties raise ValueError rather than silently comparing scales.
Legacy/mock solutions without a common recorded penalty use stored aggregate
metrics, but numerical deltas involving unranked rows are None with an explicit
summary notice. Missing required aggregate indicators raise KeyError, not fake
zero deltas. Team A may need explicit error presentation for incompatible legacy
comparisons in later integration; no UI modifications are included here.


## Milestone 5 — contract execution and persistence

AssignmentEngine registers PREFERENCE, SKILL_FIT, and BALANCED. execute_run now
validates direct requests, generates alternatives, builds real Solution objects,
and persists the resulting AssignmentRun. run_assignment continues delegating
through RunRequest. No public signatures or domain models changed.

Validation happens before optimization or cohort writes. Structural errors yield
INVALID_INPUT; pure mathematical validation failures yield INFEASIBLE. Both are
stored as runs with no solutions and no cohort synchronization. Settings use the
existing accepted strategy names and K=1–4. Notes, engine identity, selected
strategy, K, PuLP version, per-solve time limit, and cohort M are recorded.

If skills is None, referenced skills must already exist in the injected
repository's database. Missing rows yield INVALID_INPUT with explicit IDs and a
request to supply a catalog. No synthetic Skill rows are created. An explicitly
empty catalog still rejects all skill references even if rows exist in the DB.
validate_inputs remains the existing stateless domain check; the persistence
reference check happens only in execute_run.

Search status mapping:

| Search result | RunStatus |
| --- | --- |
| K_REACHED / EXHAUSTED | COMPLETED |
| Initial INFEASIBLE | INFEASIBLE |
| INVALID_INPUT | INVALID_INPUT |
| NOT_SOLVED / NON_OPTIMAL_INCUMBENT | WARNING |
| FAILED / DUPLICATE / invalid solution construction | FAILED |

Earlier verified solutions are retained on later interruption/failure. Initial
infeasibility reasons are exposed at run level; proof of exhaustion remains in
search-attempt diagnostics without labeling earlier solutions infeasible.
Successful runs may still contain input warnings. Run status is not a claim of
objective optimality; each solution retains its own proof flag. The elapsed solve
time is summed across attempts. distinct_alternatives reflects built solutions.

For runs containing solutions, supplied skills, projects, students, and locks
are upserted in foreign-key order and then the complete run is saved inside one
shared transaction using self.run_repo.db. Any SQLite error propagates to the
caller and rolls back all those writes. A failed persistence operation cannot
truthfully return a persisted FAILED run, so it raises instead. Database schema
initialization is the responsibility of the caller/application, as before.

No cohort replacement or history-clearing methods are called. Entities and locks
not supplied are not deleted; the request defines the solving cohort/locks for
that run. Historical assignment rows retain their decisions and stored metrics;
current entity names/profiles may be updated by upserts. The schema does not
store full historical input snapshots. Repositories list runs with solution
metadata; get_run/get_solution provide full assignments, preserving existing
retrieval behavior. Full application test hardening remains Milestone 6.
