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

The following decisions remain open:
- Exact preference scoring function
- Exact skill compatibility scoring function
- Score normalization
- Relative objective weights
- Handling of unranked projects
- Supported strategy keys

Do not silently invent or finalize these decisions. Inspect the repository for existing definitions and report unresolved questions.

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

## Milestone 1 implementation (2026-10-22)

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
