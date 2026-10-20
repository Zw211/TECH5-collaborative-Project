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
- Case boxes started unchecked for team review. We update them as work is
  verified. Some starter behaviour already works; an unchecked box does not
  necessarily mean code is missing.
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

- [x] CAP-01 **Missing or non-integer capacities** - reject before calculations. Cover `None`, blank text, numeric text passed directly to the engine, fractions, booleans, and non-finite numbers. Forms may parse valid text into integers before calling the engine.

  Tests written: `test_minimum_capacity_must_be_an_integer` and
  `test_maximum_capacity_must_be_an_integer` in `tests/test_validation.py`.
  Each runs with 12 invalid values. Before implementation on 2026-10-20,
  all 24 examples failed: the validator could crash, accept the value, or
  report the wrong kind of error.

  Implemented and verified on 2026-10-20: a separate check now inspects
  both capacity types for every project before capacity calculations.
  Only Python integers are accepted, excluding floats and booleans. It
  collects errors naming the project and field, then returns invalid input
  if any capacity has the wrong type. All 24 original examples now pass.
  `test_capacity_type_errors_are_reported_together` and
  `test_contract_rejects_non_integer_capacity` also pass, covering several
  bad fields together and the engine interface used by Team A.

  Latest focused result: **40 passed**. Latest full-suite result:
  **4 failed, 118 passed, 12 xfailed**. The remaining four failures are
  CAP-04's real-engine tests. See the implementation notes below.

- [x] CAP-02 **Negative minimum or non-positive maximum capacity** - reject. Under the existing schema, minimum must be at least 0 and maximum at least 1.

  Evidence: `test_negative_minimum_capacity_is_rejected` checks -1 and -2;
  `test_non_positive_maximum_capacity_is_rejected` checks 0 and -1.
  All four examples passed on 2026-10-20 using the existing validator.

- [x] CAP-03 **Minimum capacity is larger than maximum capacity** - reject and identify the project and conflicting values.

  Evidence: `test_capacity_errors` checks minimum 5 and maximum 2.
  Its error-message assertion now also checks that P1 and both conflicting
  values are identified.
  This test passed on 2026-10-20 using the existing validator.

- [ ] CAP-04 **Capacity exactly at a boundary** - accept otherwise feasible allocations with headcount equal to the minimum or maximum. Minimum 0 and minimum equal to maximum are valid input bounds.

  Input-validation evidence: `test_zero_minimum_capacity_is_allowed`,
  `test_cohort_at_minimum_capacity_is_allowed`,
  `test_cohort_at_maximum_capacity_is_allowed`, and
  `test_equal_minimum_and_maximum_capacity_is_allowed` all passed on
  2026-10-20. These show that valid boundary inputs are accepted.
  Output tests are also written: `test_real_engine_accepts_capacity_boundaries`
  in `tests/test_solvers.py` tries the same four boundary cases. All four
  fail with `NotImplementedError` because the real engine's `execute_run()`
  is unfinished. The checkbox remains open until those output tests pass.
  That output work is related to OUT-04.

### Capacity test walkthrough

Most test functions below are in `tests/test_validation.py`.
They use the existing `Student`, `Project`, and, where needed,
`FixedAssignment` classes. Each makes a small example, calls
`validate_cohort()`, then uses `assert` to check the returned result.
An assertion fails if its condition is false. These validation tests do
not create assignments or use the database. The interface test is in
`tests/test_contract_and_engine.py` and calls `engine.validate_inputs()`.
The actual output test is in `tests/test_solvers.py`.

| Test | Example and expected result |
| --- | --- |
| `test_minimum_capacity_must_be_an_integer` | One student, maximum 3, and an invalid minimum. Expect invalid input, an error naming P1 and its minimum capacity and asking for a whole number, and no mathematical infeasibility claim based on the invalid value. |
| `test_maximum_capacity_must_be_an_integer` | One student, minimum 0, and an invalid maximum. Expect the same checks, but the message must identify the maximum capacity. |
| `test_capacity_type_errors_are_reported_together` | Two students and three projects. P1 and P2 have four invalid capacity fields in total; P3 is valid but has only one place. Expect all four field errors and no claim of a shortage based only on P3. |
| `test_contract_rejects_non_integer_capacity` | Send a `RunRequest` with maximum capacity `"2"` to `engine.validate_inputs()`. Expect a `ValidationOutcome` that rejects the input, identifies P1 and its maximum, and does not claim mathematical infeasibility. |
| `test_negative_minimum_capacity_is_rejected` | One student, maximum 3, and minimum -1 or -2. Expect invalid input and an error identifying P1's negative minimum. |
| `test_non_positive_maximum_capacity_is_rejected` | One student, minimum 0, and maximum 0 or -1. Expect invalid input and an error identifying P1's non-positive maximum. |
| `test_capacity_errors` | One student and P1 with minimum 5 and maximum 2. Expect invalid input and a message saying P1's minimum exceeds its maximum. This strengthens the existing starter test. |
| `test_zero_minimum_capacity_is_allowed` | One student and a project with minimum 0 and maximum 1. Expect valid input and no feasibility problem detected by these checks. This also checks the smallest valid maximum, 1. |
| `test_cohort_at_minimum_capacity_is_allowed` | Two students and one project with minimum 2 and maximum 3. Expect acceptance: having exactly the minimum number of students is allowed. |
| `test_cohort_at_maximum_capacity_is_allowed` | Two students, both fixed to the only project, with minimum 1 and maximum 2. Expect acceptance: neither the total cohort nor the number of locks exceeds the maximum. |
| `test_equal_minimum_and_maximum_capacity_is_allowed` | Two students and one project with minimum 2 and maximum 2. Expect acceptance: a project may require an exact headcount. |
| `test_real_engine_accepts_capacity_boundaries` | Run the real engine for each of the four valid boundary examples above, fixing the students to P1. The zero-minimum example also includes P2 with minimum 0, which must stay empty. Expect one completed solution containing every student exactly once, all assigned to P1, with headcount between the bounds. |

The first two tests share `INVALID_CAPACITIES`: `None`, empty text, spaces,
`"2"`, `"two"`, `1.5`, `2.0`, `True`, `False`, not-a-number, positive infinity,
and negative infinity. Numeric text belongs to form parsing; direct engine
input must already contain integers. A whole-looking float such as `2.0`
still has the wrong type. Booleans are not headcounts even though Python
can treat them like 1 and 0. The non-finite values are not usable headcounts.

`@pytest.mark.parametrize` tells pytest to run the same test separately
for each listed value. `pytest.param(..., id="...")` gives the example a
readable name in the results. This gives 24 independent CAP-01 examples,
so the first failure does not prevent pytest from trying the other values.

The `object` type hint lets the two test functions receive deliberately bad
inputs. `# type: ignore[arg-type]` tells a static type checker that passing
the wrong type to `Project` is intentional in this test; it does not catch
exceptions, change the value, or skip the test.

For rejected inputs, `is_valid is False` checks the decision.
`any(... for error in result.errors)` checks that at least one returned
message explains the specific problem and identifies P1. The CAP-01 tests
also require an empty `infeasibility_reasons` list: invalid values must be
rejected before using them to claim a mathematical capacity shortage.

For accepted boundaries, the four assertions check that the input is valid,
the preliminary checks detect no infeasibility, and both error lists are
empty. Missing preference lists can produce warnings in these small
capacity-only examples; that does not make the capacity bounds invalid.
These validation tests do not check assignments returned by the solver.

The additional real-engine test uses `tmp_path`, a temporary folder pytest
provides for each example. `create_app()` points the test at a new SQLite
file there, keeping the application's normal database separate. A simple
loop builds one or two students, each ranking P1 first and fixed to P1.
Locks keep the expected allocation unambiguous. In the zero-minimum case,
an extra project P2 has minimum 0 and must remain unused. This checks that
zero is allowed as the actual headcount of an optional project too.
The test creates a `RunRequest` asking for one alternative, then calls the real
`AssignmentEngine.execute_run()` rather than the mock.

Its assertions require a completed run with one solution. The number of
assignments must equal the number of supplied students, and the returned
student IDs must exactly match the supplied IDs. Together, these two checks
catch duplicate or missing students. Every assignment must refer to P1,
and the final headcount must respect both bounds, including equality.
The same four sets of bounds and student counts run as separate tests.
All four currently stop at `execute_run()` with `NotImplementedError`;
none reaches the output assertions yet.

First focused run on 2026-10-20:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_validation.py -q --tb=short
```

Result: **24 failed, 14 passed**. CAP-01 accounts for all 24 failures. The
passing tests include CAP-02, CAP-03, CAP-04 input checks, and the five
other existing validation tests. Pytest also reported two cache-writing
warnings; they do not account for the assertion failures or type errors.
No new tests were marked as expected failures. Validator code was unchanged
during that earlier test-writing step.

Full-suite verification of the earlier test-writing step, before CAP-01
was implemented:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=no -p no:cacheprovider
```

Result at that stage on 2026-10-20: **28 failed, 92 passed, 12 xfailed**. There were
24 failures for CAP-01's missing integer checks and four failures for
CAP-04's unfinished real engine. The 12 expected failures belong to existing
unfinished features. The first full run encountered sandbox restrictions
on pytest's temporary folders; the reported result is from the authorized
rerun with access to those folders. Cache writing was disabled for that
run; disabling the cache does not change assertion behaviour.

### CAP-01 implementation and latest verification

`validate_cohort()` now checks both capacity types for every project before
the existing range checks or calculations. The code uses a normal loop and
two `if` statements:

```python
type(project.min_capacity) is not int
type(project.max_capacity) is not int
```

These expressions detect values that are not Python integers. This also
rejects `True` and `False`, whose type is `bool`, and `2.0`, whose type is
`float`. No conversion is attempted inside the validator; form parsing
should already have converted valid number text into integers.

`has_invalid_capacity` starts as `False`. Finding a bad field adds a clear
error and sets the flag to `True`. The loop keeps checking so all bad
capacity fields can be reported together. After the loop, a true flag
makes the function set `is_valid` to `False` and return the result before
capacity calculations or fixed-assignment comparisons. Other checks can
continue when the caller corrects these values and validates again.

For example, a text maximum for P1 gives this message:

```text
Project 'P1': maximum capacity must be a whole number.
```

The existing negative-capacity and inverted-bound checks still run when
the types are correct. Zero remains a valid minimum and one remains a
valid maximum. The public component contract is unchanged.

The two added regression tests check more than single bad values:

- `test_capacity_type_errors_are_reported_together` checks that both bad
  fields in P1 and both in P2 are reported. It also catches an incorrect
  approach that skips those projects and reports a shortage using only
  valid P3's one place for two students.
- `test_contract_rejects_non_integer_capacity` checks that Team A can receive
  the same clear rejection through the engine's existing interface.

Focused check on 2026-10-20:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_validation.py tests/test_contract_and_engine.py::test_contract_rejects_non_integer_capacity -q -p no:cacheprovider
```

Result: **40 passed** (39 validation examples and the new contract example).
The full-suite command shown above then returned **4 failed, 118 passed,
12 xfailed**. All 24 original CAP-01 examples and both new regression tests
pass. Only CAP-04's four real-engine examples fail because `execute_run()`
is still unimplemented. The branch therefore still does not meet the
repository's passing full-suite requirement.

There are now 12 capacity-related test functions covering 39 examples:
26 for CAP-01, four for CAP-02, one for CAP-03, and eight for CAP-04
(four input checks and four real-engine output checks).

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

Capacity tests for CAP-01 to CAP-04 are written, and CAP-01's integer checks
are now implemented and passing. CAP-04's output tests will be completed by
implementing the real engine using the approved assignment method. Next
input-validation priorities are SKILL-02, SKILL-03, and PREF-06.
For each small change, run the relevant tests and update its evidence before
moving on. Review policy questions
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
inspection of the starter code and tests. Updated on the same date with
CAP-01 to CAP-04 tests, observed results, a plain-language walkthrough,
and the CAP-01 implementation and its two regression tests. The project
`tech5-simple-oop` skill was also updated to explain the purpose and scope
of approval requests in everyday words.
Responses remain proposed unless recorded as verified above. Student
understanding of the changes has not yet been demonstrated.
