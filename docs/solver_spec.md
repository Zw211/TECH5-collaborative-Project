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

Support up to K distinct feasible assignments, with K = 3 as the default.

Two solutions are distinct only if at least one student's project assignment differs.

Different objective weights may produce identical assignments. The implementation must detect duplicates.

Do not manufacture additional solutions when fewer than K feasible alternatives exist.

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
