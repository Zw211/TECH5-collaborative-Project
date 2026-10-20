# Input and output validation checklist

This is Team B's working list of things that could go wrong with the data,
the assignment results, or saving and loading them. It covers the situations
in the course brief and additional examples found while reviewing the starter.

The responses below are **proposals for team discussion**, unless described
as an existing rule. A warning means the application may continue while
explaining the problem. Rejecting input means the data must be corrected.
Infeasibility means the agreed hard constraints cannot all be satisfied.
A database failure means an operation failed; it does not prove infeasibility.

## How we use the checkboxes

- Change `[ ]` to `[x]` when we agree on the response, implement it, and have
  passing tests that check the intended behaviour.
- Add the test name and result below that item. Keep the item visible so
  we retain the reason for the rule.
- An expected failure (`xfail`) is unfinished work, so it stays unchecked.
- All case boxes start unchecked for team review. Some starter behaviour
  already works; an unchecked box does not necessarily mean code is missing.
- Use synthetic records in tests. Include valid examples that should be
  accepted, as well as bad examples that should be detected.

Example evidence to add after completing an item:

```text
Evidence: tests/test_validation.py::test_capacity_errors
Result: passed on YYYY-MM-DD. Example: minimum 5, maximum 2 was rejected.
```

## Where we work

| Area | Main implementation | Main tests |
| --- | --- | --- |
| Input checks and obvious feasibility problems | [app/domain/validation.py](../app/domain/validation.py), especially `validate_cohort()` | [tests/test_validation.py](../tests/test_validation.py) and the validation cases in [tests/test_edge_cases.py](../tests/test_edge_cases.py) |
| Validation through the interface Team A uses | `AssignmentEngine.validate_inputs()` in [app/engine/solvers.py](../app/engine/solvers.py) | [tests/test_contract_and_engine.py](../tests/test_contract_and_engine.py) |
| Producing feasible, distinct assignments | `execute_run()` and the strategies in `app/engine/solvers.py` | [tests/test_solvers.py](../tests/test_solvers.py) and `tests/test_edge_cases.py` |
| Checking and comparing result measures | [app/engine/metrics.py](../app/engine/metrics.py) | [tests/test_metrics.py](../tests/test_metrics.py) |
| Saving and loading safely | [app/persistence/database.py](../app/persistence/database.py), [repositories.py](../app/persistence/repositories.py), and [schema.sql](../app/persistence/schema.sql) | [tests/test_persistence.py](../tests/test_persistence.py) and integration tests |
| Showing understandable messages | Team A's routes and templates, using the engine's returned errors and warnings | UI and integration tests with Team A |

Start with the input checks this week. Plan the solver, result, and database
cases now; implement them alongside the relevant component. Shared domain,
database, and contract changes need coordination with Team A.

## Student, project, and skill identifiers

- [ ] ID-01 **No students** - reject the empty cohort with a clear message.
- [ ] ID-02 **No projects** - reject the empty project catalogue with a clear message.
- [ ] ID-03 **Blank identifiers** - reject student, project, or skill IDs that are empty or only spaces.
- [ ] ID-04 **Identifiers of the wrong type** - reject IDs that are not text, without crashing when comparing or looking them up.
- [ ] ID-05 **Duplicate identifiers** - reject repeated IDs within the student, project, or skill catalogue. Similar display names alone do not establish duplicate identity.
- [ ] ID-06 **Duplicate skill names** - reject conflicting names before saving, consistently with the database's unique skill-name rule. Decide how case and spaces are treated.
- [ ] ID-07 **A record refers to the wrong parent** - reject, for example, a preference inside student S1 whose `student_id` is S2, or a requirement inside P1 whose `project_id` is P2.
- [ ] ID-08 **Differences in case or spaces** - agree on a consistent rule across forms, engine, and database. Explain unmatched IDs; avoid silently merging distinct records.

## Project preferences supplied by students

- [ ] PREF-01 **Incomplete project preferences from a student** - we are assuming a warning is enough, pending team confirmation. Warn when fewer than three projects are ranked, as the brief expects at least three. Also explain when fewer than three projects are offered.
- [ ] PREF-02 **No preferences at all** - we are assuming a warning, pending confirmation. Explain that the student may receive an unranked project; agree on scoring before using this in the solver.
- [ ] PREF-03 **The same project appears twice in one student's list** - propose rejecting the duplicate and asking for a correction. The current validator warns, but the database cannot store duplicate student/project preferences.
- [ ] PREF-04 **One student gives two projects the same rank** - decide the tie policy. Propose rejecting until ties can be represented consistently: the current validator warns, but the database requires unique ranks per student.
- [ ] PREF-05 **Several students want the same project** - accept this as normal competition. The solver must respect capacity and explain how competing preferences are handled.
- [ ] PREF-06 **Invalid preference ranks** - reject zero, negative numbers, fractions, text, missing values, or booleans. A rank should be a positive whole number.
- [ ] PREF-07 **Gaps in the ranks, such as 1, 3, 7** - decide whether these are allowed positions or mistaken input. Warn or reject according to the agreed rule; do not silently change the ranks.
- [ ] PREF-08 **A preference refers to an unknown project** - reject the reference and identify the affected student and project.

## Student skills and project requirements

- [ ] SKILL-01 **Missing skills from a student's profile** - we are assuming the student remains assignable and missing skills count as level 0 for matching, pending confirmation. Do not invent proficiency; mandatory requirements still apply.
- [ ] SKILL-02 **Invalid student skill levels** - propose rejecting stored levels outside 1 to 5, fractions, text, missing values, and booleans. Agree that no skill is represented by an omitted entry; the UI currently omits level 0 entries.
- [ ] SKILL-03 **Invalid project requirement levels** - reject required levels outside 1 to 5 or values that are not whole numbers.
- [ ] SKILL-04 **An unknown skill is used in a profile or requirement** - decide the policy. Propose rejecting before persistence, since the database requires a matching skill record. The current validator only warns when a nonempty catalogue is supplied.
- [ ] SKILL-05 **The skill catalogue is absent or empty** - distinguish an omitted optional catalogue from an explicitly supplied empty one. Decide how references can be verified; avoid accidentally skipping checks because the list is empty.
- [ ] SKILL-06 **A project has no skill requirements** - accept the project. Define its skill-fit score explicitly and avoid dividing by zero; the starter edge-case test expects a score of 1.0.
- [ ] SKILL-07 **Repeated or conflicting requirements for one skill** - propose rejecting duplicates for correction rather than silently overwriting a requirement.
- [ ] SKILL-08 **An invalid mandatory-skill flag** - reject unsupported flag values at the relevant input boundary. For example, text such as "false" must not accidentally be treated as true.

## Project capacities

- [ ] CAP-01 **Missing or non-integer capacities** - reject before calculations. Cover `None`, blank text, numeric text passed directly to the engine, fractions, booleans, and non-finite numbers. Forms may parse valid text into integers before calling the engine.
- [ ] CAP-02 **Negative minimum or non-positive maximum capacity** - reject. Under the existing schema, minimum must be at least 0 and maximum at least 1.
- [ ] CAP-03 **Minimum capacity is larger than maximum capacity** - reject and identify the project and conflicting values.
- [ ] CAP-04 **Capacity exactly at a boundary** - accept otherwise feasible allocations with headcount equal to the minimum or maximum. Minimum 0 and minimum equal to maximum are valid input bounds.

## Fixed assignments

- [ ] FIX-01 **One student is fixed to different projects** - reject the conflicting instructions. Do not silently choose one lock.
- [ ] FIX-02 **The exact same fixed assignment appears twice** - decide whether to reject it or remove the duplicate with a warning. Do not count the same locked student twice when checking project capacity.
- [ ] FIX-03 **A lock refers to an unknown student or project** - reject with a message identifying the missing record.
- [ ] FIX-04 **Locks exceed a project's maximum capacity** - report that the locks and capacity cannot all be satisfied. Preserve the locks until a human corrects the inputs.
- [ ] FIX-05 **An unsupported fixed-assignment status** - agree which statuses create active locks. Reject or explain unsupported values rather than silently ignoring a lock.

## Feasibility and project demand

Passing input checks does not prove that a feasible assignment exists.
The solver must check combinations of constraints as well.

- [ ] FEAS-01 **More students than total places** - report infeasibility when every student must receive a project. Partial allocation requires an explicitly agreed policy and clearly identified unassigned students.
- [ ] FEAS-02 **Too few students to fill all required minimum capacities** - report infeasibility under the current model requiring every project's minimum.
- [ ] FEAS-03 **A required mandatory skill is unavailable** - report infeasibility when that coverage is required by the agreed model. State whether coverage is required from one team member or every assigned student; the report proposes team coverage.
- [ ] FEAS-04 **Enough places overall, but the constraints clash** - use the solver to detect cases such as two required projects competing for the only qualified student, or locks preventing mandatory skill coverage.
- [ ] FEAS-05 **Very high or low preference demand for one project** - accept the preferences. Demand alone does not prove infeasibility; check capacities and other hard constraints, then show the trade-off.
- [ ] FEAS-06 **A project can have zero students** - decide whether mandatory skill coverage still applies when the project is unused. Document that rule before reporting an unused project as infeasible; do not assume minimum 0 resolves this question.

## Run settings

- [ ] RUN-01 **Unknown assignment strategy** - reject an unsupported strategy with a clear message rather than silently choosing another one.
- [ ] RUN-02 **Invalid number of requested alternatives** - reject missing or non-positive values and values that are not whole numbers. Document any supported upper limit rather than inventing one silently.

## Assignment output and comparisons

These checks apply to the real engine even when Team A can already display
mock results. Mock output is evidence of the UI workflow, not proof that the
real optimization method works.

- [ ] OUT-01 **A student is assigned more than once** - treat the result as invalid. Do not present it as a feasible solution.
- [ ] OUT-02 **A student is omitted** - treat it as invalid under exact allocation. Only return a partial result under an explicitly allowed policy, listing unassigned students and reasons.
- [ ] OUT-03 **An assignment contains unknown student or project IDs** - treat it as invalid and identify the reference.
- [ ] OUT-04 **A result breaks capacity, mandatory-skill, or fixed-assignment rules** - treat it as invalid. Verify these rules against the actual returned assignments.
- [ ] OUT-05 **A student receives an unranked project** - follow the agreed policy, flag the allocation, and include it in the unranked count. Define its treatment in preference and fairness measures.
- [ ] OUT-06 **Only one alternative is found** - return the one actually found and explain the search outcome. Claim that only one feasible solution exists only when uniqueness has been established.
- [ ] OUT-07 **Duplicate alternatives** - remove or prevent repeated student-to-project allocations. Changing row order, strategy labels, or scores does not create a distinct solution.
- [ ] OUT-08 **Equal aggregate scores** - keep distinct allocations available for comparison. Explain individual differences and use a documented tie policy for recommendations; an equal score does not make input invalid.
- [ ] OUT-09 **No feasible solution exists** - return an infeasibility result with reasons and zero claimed feasible alternatives.
- [ ] OUT-10 **The solver stops early or fails** - distinguish a time limit, failure, and an unfinished search from proven infeasibility. Report any feasible result actually verified and the search limits; do not claim optimality without evidence.
- [ ] OUT-11 **Fewer than K alternatives are returned** - explain why and report the actual count. Return at most K distinct verified feasible solutions; do not invent alternatives to fill the request.
- [ ] OUT-12 **Incorrect or undefined result measures** - test reported ranks, skill-fit scores, capacity counts, and fairness measures against small worked examples. Handle empty results and zero denominators without misleading numbers or crashes.
- [ ] OUT-13 **Fairness reporting leaves students out** - include rank distribution, unranked count, worst individual outcome, and the team's justified additional fairness measure. Define how unranked or allowed unassigned students are represented.
- [ ] OUT-14 **A weighted score is presented as proof of fairness** - explain the selected weights and trade-offs. Distinguish feasibility, preference satisfaction, skill fit, and fairness in recommendations.

## Database records and failures

- [ ] DB-01 **Invalid saved records** - detect invalid references, levels, ranks, or capacities when loading. Report the affected records. Do not silently repair or drop them and claim the original cohort was solved.
- [ ] DB-02 **The database cannot be opened, read, or written** - return a useful failure message for a locked, unavailable, read-only, or damaged database. Do not label this as mathematical infeasibility.
- [ ] DB-03 **Saving fails partway through** - roll back the affected transaction so related records are not left partly saved. Report whether saving succeeded; do not claim persistence succeeded after an error.
- [ ] DB-04 **Input records change or are deleted after a saved run** - agree how history is preserved. The current schema can cascade deletion of students or projects to saved assignments; avoid presenting an altered old run as its original result.

## Existing evidence and first steps

The six tests in `tests/test_validation.py` already exercise empty datasets,
duplicate student/project IDs, inverted capacity bounds, contradictory locks,
locks exceeding capacity, and a total capacity deficit. They do not cover
every input type or every case above.

The contract test `test_contract_validate_inputs` checks a standard cohort
and an infeasible request through the engine interface. Further validation
examples already exist in `tests/test_edge_cases.py`.

Start with CAP-01, add valid boundary examples from CAP-04, then work on
SKILL-02, SKILL-03, and PREF-06. For each small change, run the relevant
tests and update its evidence before moving on. Review policy questions
such as ties, missing preferences, mandatory-skill coverage, and partial
allocation with the team rather than deciding them silently in code.

From the repository root, this checks the existing validation tests and the
engine's validation interface:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_validation.py tests/test_contract_and_engine.py::test_contract_validate_inputs -v
```

Before a pull request, run the repository's full check:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Record the date, command, and actual results when completing cases. Preserve
the current component contract and indicator keys unless a change has been
coordinated with both teams. Instructor approval of the proposed assignment
method should be recorded separately from validation test results.

Drafted on 2026-10-20 with AI assistance from the supplied requirements and
inspection of the starter code and tests. Responses remain proposed for team
review; this document does not claim the listed features are implemented.
