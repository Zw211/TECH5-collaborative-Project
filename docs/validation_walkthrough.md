**Validation walkthrough — work compared with main on 20 October 2026**

This guide explains the changes from main at `023e00e` to `teamB/input_validation` at `8e784ec`. GitHub was fetched before comparison. Main is an ancestor of this branch, so the direct comparison and the changes since the common ancestor are the same. There are 11 branch commits from today, affecting 24 tracked files before adding this guide.

The short progress record remains [the checklist](input_output_validation_checklist.md). This longer guide is for learning and discussion. AI helped with the code, tests, and explanations; reading the guide alone does not establish student understanding.

**1. What the comparison establishes**

| Version | Passed | Expected failures | Ordinary failures | Collected examples |
| --- | ---: | ---: | ---: | ---: |
| Current main, tested in an isolated temporary copy during this review | 84 | 12 | 0 | 96 |
| Our branch, latest recorded full run at the reviewed commit | 440 | 12 | 4 | 456 |

Collection was also checked during this review: the branch contains 456 examples. We added 107 test functions that expand into 361 examples. One older form test was replaced, giving a net increase of 360 examples. Three other existing test functions were strengthened or changed. A parameterized function can count as many examples; 361 examples does not mean 361 separately written functions.

The four ordinary failures are new tests we added for actual solver output at capacity boundaries. They call the real `execute_run()`, which already raised `NotImplementedError` on main. Their assignment assertions are never reached. They remain unfinished work, and the full branch suite is not green. The 12 expected failures cover other unfinished starter features; an expected failure is not a successful implementation.

These are comparisons with current main. They are not confirmation of the earlier historical claim that the first starter run had 36 passed and 15 expected failures.

**2. The application objects and layers**

A student object holds its ID, name, skill levels, and preferences. A project object holds its ID, capacities, and requirements. A skill object describes a catalogue entry. A preference connects a student ID to a project ID and rank. A fixed assignment locks one student to one project.

An identifier is a record's code, such as `S1` or `P1`. A reference is a code used to connect to another record: a preference containing `project_id="P1"` refers to that project. A catalogue is the list of available records.

`Student`, `Project`, `Skill`, and the other domain classes already existed. So did `Student.get_skill_level()`, which returns 0 for an omitted skill. We reused them.

The normal run path is:

`form text → form parser → saved records → RunRequest → AssignmentEngine.validate_inputs() → domain validation → ValidationOutcome → reject or continue`

Before loading run inputs, a database integrity check examines broken references and raw mandatory flags. Validated requests still reach the explicit mock demonstration while the real engine is unfinished.

| File | Responsibility and change |
| --- | --- |
| [domain/validation.py](../app/domain/validation.py) | Existing cohort validator expanded with focused helpers, stricter checks, and preliminary feasibility checks. |
| [visualization/forms.py](../app/visualization/forms.py) | New student-skill and run-setting parsers; stricter project requirement parsing. |
| [engine/solvers.py](../app/engine/solvers.py) | Existing validation interface now checks run settings; convenience method preserves an omitted catalogue. The solver is still unfinished. |
| [engine/metrics.py](../app/engine/metrics.py) | Only the no-requirements skill-fit case is implemented: `(1.0, [])`. |
| [visualization/routes.py](../app/visualization/routes.py) | Enforces rejection before writes/runs and coordinates safe scenario loading and reruns. |
| [persistence/database.py](../app/persistence/database.py) | Adds integrity checks, strict saved flag reading, configurable lock timeout, and a shared transaction facility. |
| [persistence/repositories.py](../app/persistence/repositories.py) | Adds atomic cohort replacement and strict mandatory-flag loading in both project loaders. |
| [contract/mocks.py](../app/contract/mocks.py) | Passes the chosen database manager to all repositories so mock writes share a transaction. The mock algorithm is unchanged. |
| [app/__init__.py](../app/__init__.py) | Handles startup and runtime database errors and invalid saved records. |
| [database_error.html](../app/visualization/templates/database_error.html) | Displays the useful error message and affected records. |
| [the checklist](input_output_validation_checklist.md) | Records policies, evidence, and unfinished cases. |

The other 13 changed files are test modules, catalogued below. The domain models, component contract, database schema, and dashboard choices are unchanged. Tests in `test_metrics.py`, `test_persistence.py`, and `test_component_integration.py` were not edited; they still form part of the suite.

The object-oriented design is visible in the form, repository, database-manager, and engine objects, each with a focused responsibility. Stateless validation rules are ordinary functions because they do not need their own persistent object state.

**3. How validation reports an outcome**

The existing `ValidationResult` object holds `errors`, `warnings`, `is_valid`, `is_feasible`, and `infeasibility_reasons`. The engine copies these into the existing contract's `ValidationOutcome`, so Team A receives the agreed shape of result.

| Situation | Example | Meaning |
| --- | --- | --- |
| Input error | Capacity is `"many"`, or a preference refers to `P99` which does not exist | Correct the data before assigning anyone. |
| Warning | A student ranks only two projects | The application may continue, with an explanation. |
| Proven preliminary infeasibility | Two distinct students are locked into a project with one place | The valid hard requirements cannot all be satisfied. |
| Database failure | A database is locked or cannot be written | The operation failed. This says nothing about mathematical feasibility. |

The current implementation also puts detected infeasibility messages in `errors`, so infeasible input makes `is_valid` false too. Do not treat the two flags as completely independent categories. The reasons list and recorded run status identify the kind of failure.

A particularly important limitation: `is_feasible=True` means these preliminary checks did not disprove feasibility. It is not proof that a complete assignment exists.

**4. The order inside validate_cohort()**

Read [validate_cohort()](../app/domain/validation.py#L433) as a coordinator:

1. Reject an empty student list or project list. If both are empty, return both errors.
2. Check IDs, nested reference IDs, ownership, and skill names. Return before using unusable or duplicate IDs for demand calculations.
3. Check capacity types. Return before comparing or adding values of the wrong type.
4. Collect skill data errors.
5. Check capacity ranges. Return before calculating shortages from invalid bounds.
6. Calculate total minimum and maximum capacities.
7. Add small-catalogue warnings and validate each student's preferences.
8. Validate fixed assignments with the shared lock validator.
9. Check total capacity shortages. These independent checks can still report a real capacity contradiction alongside other non-capacity input errors.
10. If errors exist, return before using bad skill or preference data in mandatory coverage checks.
11. Check necessary mandatory team coverage and usable places, then return the result.

An early `return` is a guard: later operations assume the earlier checks passed. It prevents a missing value from being compared with a number, a list from being used as a set key, or duplicate student records from being counted as two real students.

The leading underscore in names such as `_validate_preferences` indicates an internal helper. It is a naming convention, not a special access restriction.

**5. Identifiers, ownership, and skill names**

Main already checked blank and duplicate student/project IDs. It did not consistently require text, validate skill catalogue IDs, check nested owner IDs, or reject padded IDs.

[_validate_identifier()](../app/domain/validation.py#L53) now requires a string that is nonempty after `strip()` and has no leading/trailing whitespace. `strip()` is used to inspect the value; the domain validator does not silently rewrite it. Text `"7"` is valid, but number `7` is not.

[_validate_identifiers()](../app/domain/validation.py#L72) applies that rule to students, projects, skills, preference owners/projects, student-skill keys, requirement owners/skills, and fixed assignment references. Sets remember IDs already encountered. Duplicate IDs are rejected within each catalogue. A student and a project may both have ID `"7"` because their catalogues are separate.

Ownership matters even when both referenced records exist. A preference inside student S1 must have `student_id="S1"`. A requirement inside project P1 must have `project_id="P1"`.

Stored IDs are case-sensitive: `P1` and `p1` can be different projects. Display names/titles need not be unique in the domain validator. Skill names have a different rule: [_validate_skill_names()](../app/domain/validation.py#L136) compares `name.strip().casefold()`, so `" Python "` and `"PYTHON"` conflict. `casefold()` handles international letter case, including the test's `Straße`/`STRASSE` example.

The skill creation route already lowercased new skill IDs and compared names without case differences. We extended the name comparison to ignore spaces on already saved names too.

The preference form already trimmed entered text. We changed its lookup to try an exact ID first, then accept a case-insensitive match only if exactly one record matches. With both `ProjectA` and `projecta` available, `PROJECTA` is ambiguous and rejected. This avoids the old case-map behaviour that could choose one record accidentally.

These tests prove clear rejection and correct matching for the listed inputs, including lists/dictionaries that would otherwise crash a set lookup. They do not establish a universal rule that every application must use case-sensitive IDs.

**6. Preferences**

Main already rejected unknown preferred projects and warned about no preferences, duplicate projects, and tied ranks. It did not enforce positive integer ranks or ranks without gaps.

[_validate_preferences()](../app/domain/validation.py#L157) uses three sets: previously seen projects, previously seen ranks, and distinct available projects with valid rank types. It now:

- Warns for no preferences or fewer than three valid distinct choices, mentioning possible assignment to an unranked project.
- Explains when fewer than three projects are offered.
- Rejects repeated projects, tied ranks within one student, unknown projects, and invalid ranks.
- Requires the rank set to equal `{1, 2, ..., N}` after individual entries pass.

For example, `1,3,7` and a single rank `2` are rejected. Records arriving in order `3,1,2` are accepted when the ranks themselves are exactly 1 through 3. Domain validation does not reorder records or renumber them.

`type(rank) is int` rejects `True` even though Python treats booleans as a kind of integer in some operations. It also rejects `2.0` and `"2"` as domain ranks. The form parser may deliberately convert text first.

Several students ranking P1 first is normal competition. It is not a tie within one student's list and is not rejected just because P1 is popular.

The preference form receives comma-separated projects, not explicit ranks. It creates ranks from their entered order. It previously silently dropped repeated projects; now repeated IDs and aliases are errors, and rejected edits preserve the old student.

Warnings are the working branch policy for incomplete preferences. Rejecting ties agrees with the existing database's unique student/rank constraint. Rejecting gaps was explicitly chosen by the user. None of this defines unranked scoring or decides who wins a popular project.

**7. Skills and project requirements**

Main warned about unknown skill references when a nonempty catalogue was supplied. It did not comprehensively check levels, boolean flags, repeated requirements, or distinguish an absent catalogue from a supplied empty one.

[_validate_skill_level()](../app/domain/validation.py#L222) requires exact integer levels 1 through 5. [_validate_skill_data()](../app/domain/validation.py#L228) applies it to profiles and requirements, checks catalogue references, rejects duplicate skill requirements, and requires real Python `True`/`False` mandatory flags.

An omitted profile entry means level 0 through the existing `get_skill_level()` method. A stored entry `{"py": 0}` is invalid. Missing a desired optional skill is permitted; missing coverage for a required mandatory skill can make a project unusable.

| Catalogue argument | References present | Result |
| --- | --- | --- |
| `None` | Yes | Warn that catalogue membership cannot be checked. |
| `[]` | Yes | Reject the references: the supplied catalogue defines no skills. |
| Supplied list | Yes | Reject any skill ID outside that list. |
| `None` or `[]` | No | No missing-catalogue warning is needed. |

We fixed `run_assignment()` to pass `skills=skills` instead of `skills=skills or []`. The older expression converted both None and an empty list into an empty list, losing the distinction.

In [StudentSkillsForm](../app/visualization/forms.py#L35), HTML text such as `" 5 "` becomes integer 5. Blank text or zero means omit that skill. Values such as `"6"`, `"2.0"`, and unknown skill fields produce errors. Both student creation and editing use the same class. The old routes sometimes ignored malformed skill text and continued saving.

[ProjectForm](../app/visualization/forms.py#L74) already parsed project fields and capacities. We added rejection for unknown requirement fields and strict checkbox parsing. Unchecked/missing or empty means False; `"1"` and `"on"` mean True. Text `"false"` is rejected. Python's `bool("false")` would be True because the string is nonempty, which explains why blind conversion is unsafe.

A zero/blank optional requirement remains omitted by the existing form convention. A checked mandatory requirement needs a valid level.

In [calculate_assignment_skill_fit()](../app/engine/metrics.py#L13), a project with no requirements returns `(1.0, [])`: nothing is unmet. This is the only scoring case we implemented. Scores for projects with requirements, fairness calculations, and comparisons remain unfinished.

**8. Capacity values and preliminary feasibility**

Main already rejected negative minima, nonpositive maxima, reversed bounds, and obvious aggregate shortages, provided the values were usable numbers.

We now require integer capacities before comparisons, then `minimum >= 0`, `maximum >= 1`, and `minimum <= maximum`. All invalid bounds are reported before returning. A project with minimum 5 and maximum 2 is rejected as bad input; those contradictory numbers are not then used to claim a meaningful shortage.

The domain validator expects already parsed numbers. The existing project form can parse numeric text and defaults a missing minimum to 0; an absent maximum is a form error. This is why rejecting domain text `"2"` does not prevent a user typing 2 in an HTML form.

Two necessary capacity checks use valid bounds:

- Under exact allocation, students exceeding the sum of maximum capacities prove a shortage.
- Students below the sum of minimum capacities cannot fill all required places.

We made the minimum-capacity check apply even when the lower-level `enforce_exact_allocation` option is False. That option does not remove project minima. It does not implement or authorize partial solver output.

Input tests accept minimum 0, equality at the minimum, equality at the maximum, and equal minimum/maximum bounds. Separate real-engine tests ask for actual assignments at those four boundaries. They currently fail at the unfinished method, so input acceptance is verified and actual solver behaviour is not.

**9. Fixed assignments**

Main checked unknown IDs, multiple lock rows for a student, and excess locked headcount. It did not clearly distinguish a repeated identical lock from two conflicting locks or validate statuses. The creation form saved directly, so the repository's upsert could overwrite an existing lock.

[validate_fixed_assignments()](../app/domain/validation.py#L276) is shared by the cohort validator and fixed-assignment form. It first checks usable capacities and IDs, then:

- Rejects an unknown student or project.
- Rejects identical repeated locks as duplicates.
- Rejects S1→P1 plus S1→P2 as a conflict and identifies both projects.
- Accepts `APPROVED`, `MANDATORY`, and `CONDITIONAL` as active locks, matching the existing form.
- Rejects unsupported statuses.
- After structural checks pass, counts distinct locked students per project and reports infeasibility when they exceed its places.

The old lock is never silently replaced by a conflicting form submission. The user must release it first. Equality with maximum capacity is valid; duplicates are corrected before any shortage calculation.

The statuses are a branch interpretation of the starter's offered values, not a new claim that CONDITIONAL means a soft solver constraint. All three are active under the current policy.

**10. Necessary mandatory team coverage**

Main asked whether any student in the cohort met each mandatory skill. It could falsely reject an optional project that could remain unused, or wrongly treat a student locked elsewhere as available.

[_check_mandatory_feasibility()](../app/domain/validation.py#L352) follows the user's confirmed rule: each used project needs at least one qualified member for each mandatory skill. Different skills may be covered by different members.

A student is a candidate only when they meet the level and are not locked to another project. If the project is already full of locked students, only its existing locked students can provide coverage.

A project must be used when its minimum is positive, someone is locked to it, or the cohort cannot fit into all other projects combined. Missing necessary coverage then proves infeasibility.

If the project can remain unused, missing coverage gives a warning that it must remain unused. Its places are excluded from usable capacity. If enough optional projects are unusable that the cohort no longer fits, that also proves a shortage.

Example: a two-person project requires Python level 3. S1 has level 3 and S2 has no Python. One qualified member is enough; we do not require both students to have Python.

Limitation: P1 and P2 can each need a Python-qualified student while only S1 is qualified. Our per-project checks may find S1 for both, but S1 cannot join both projects. The future solver must decide these combinations. A passing input check does not prove joint feasibility.

**11. Run settings, rejection, and reruns**

The dashboard already offered `PREFERENCE`, `SKILL_FIT`, `BALANCED` and one to four alternatives, with three selected. We did not add those choices.

[validate_run_settings()](../app/domain/validation.py#L417) and [RunSettingsForm](../app/visualization/forms.py#L13) now check them. Preference prioritizes ranked choices, skill fit prioritizes skills, and balanced intends a documented combination. They are recognised names; their real methods and weights are unfinished. Four is the current interface limit, not a mathematical theorem or a newly established course requirement.

The form converts text such as `" 3 "` to integer 3. Domain settings require an integer 1–4 and an exact supported strategy name. Missing or invalid posted counts are rejected instead of crashing `int()` or silently accepting an unsupported value.

Main called validation before a run but did not enforce rejection before proceeding. [_execute_validated_request()](../app/visualization/routes.py#L865) now records a rejected cohort as `INVALID_INPUT` or `INFEASIBLE`, with diagnostics and no solutions. Input errors take precedence if both kinds are present. Bad settings start no run at all. Invalid raw saved flags/references are rejected even earlier with a correction page.

Valid requests still encounter the real engine's existing `NotImplementedError` and use the explicitly announced mock demonstration. Mock results are not proof that the real solver works or that all output rules have been checked. The mock currently caps alternatives at three even if four are requested.

[lock_and_rerun()](../app/visualization/routes.py#L984) is another entry point. It now checks permissions, saved integrity, the source solution, whether the posted pair actually belongs to that solution, and the new lock together with existing locks/current inputs. It saves no lock on rejection. The valid mock run and new lock are saved together.

**12. Saved records, failures, and transactions**

SQLite's schema already had primary keys, foreign keys, and some checks, but not every business rule. For example, the level check allows values above 5, and ordinary SQLite columns do not enforce exact Python types. Old imports can also leave bad rows. We therefore validate saved data before using it.

[check_input_integrity()](../app/persistence/database.py#L79) uses `PRAGMA foreign_key_check` to find broken saved references, identifying table, row, and missing parent table. It checks raw mandatory flags before normal loading could change their meaning. [read_boolean()](../app/persistence/database.py#L24) accepts only SQLite integers 0/1. Both project-loading methods use it. Other levels, ranks, capacities, IDs, and statuses go through the shared validator after loading.

[InvalidDatabaseRecords](../app/persistence/database.py#L16) carries correction messages. The new Flask handler displays those with HTTP 422, meaning the saved data cannot be processed as supplied. SQLite operational failures get HTTP 503 and a useful read/save failure page. Startup failures display an explanation, and CSS can still load. Logging retains technical failure details.

A transaction groups related writes: either all succeed and commit, or all are rolled back. Main already had rollback inside a single `connection()` block. We added tests proving that existing student-save and run-save rollback still works. We did not invent single-repository rollback today.

The new [transaction()](../app/persistence/database.py#L124) allows multiple repository objects to share one connection and one commit/rollback boundary. The mock engine now receives that same manager for its student, project, skill, lock, and run repositories. This is dependency injection: the constructor receives the collaborator it should use.

The new [CohortRepository.replace()](../app/persistence/repositories.py#L15) replaces related scenario data in one transaction. An unknown scenario is checked before deletion, fixing a route that previously cleared data even for an unknown name. Structurally invalid scenarios are rejected; the intentionally infeasible demo can still be loaded for diagnostics.

The tests deliberately cause foreign-key errors, hold a real writer lock, open a real read-only connection, create a damaged file, and install a trigger that aborts a mock run save. They check the response AND query the saved records afterwards. The trigger test proves that a new lock is rolled back with the failed mock run.

Rollback protects failed operations. It does not make old successful runs immutable. Deleting students/projects can still cascade into saved assignments; preserving historical input/result snapshots remains DB-04.

**13. How to read the tests**

A typical unit test follows arrange → act → assert:

```python
student = models.Student("S1", "Student 1", skills={"py": True})
project = models.Project("P1", "Project 1")

result = validation.validate_cohort(
    [student], [project], [models.Skill("py", "Python")]
)

assert result.is_valid is False
assert result.infeasibility_reasons == []
```

First construct a tiny example, then call the real validator, then check the promised behaviour. Here the boolean is invalid data; we have not proved that assigning the corrected student is impossible.

`assert` makes the test fail if the condition is false. `pytest.mark.parametrize` runs the same test with several inputs. Two stacked parameter lists run every combination. `pytest.param(..., id="...")` gives an example a readable name in failure output. `# type: ignore` allows a deliberately malformed input past a development-time type checker; it does not disable runtime validation.

A set stores unique values, a dictionary associates keys with values, `append()` adds one message, and `extend()` adds messages from another list. `continue` skips the current loop item; `return` leaves the function. `any(...)` asks whether at least one entry satisfies a condition. Checking exact numeric types avoids Python treating True as 1.

Tests at different boundaries answer different questions:

| Test kind | What it verifies |
| --- | --- |
| Domain/unit | The rule returns the right errors, warnings, or preliminary infeasibility on a small example. |
| Form | HTML strings become proper values, or produce clear errors before an object is saved. |
| Contract | Team A receives the existing ValidationOutcome object and diagnostics. |
| Flask route + database | A submitted request shows the expected message and leaves the expected saved state. |
| Transaction | A failure after some writes does not leave partial changes behind. |
| Real-engine output | Actual assignments obey the rule. The four added capacity examples do not pass yet. |

`tmp_path` is pytest's separate temporary folder for each example. Database tests use separate SQLite files there. `client.post()` submits a request without opening a browser. `follow_redirects=True` follows the form's redirect to inspect the final page; a final HTTP 200 does not mean the invalid data was accepted. The tests also check messages and database rows.

`pytest.raises(...)` verifies a specific exception. `monkeypatch` temporarily substitutes a collaborator and restores it afterwards. For the read-only test, the substitute returns an actual read-only SQLite connection. For the convenience-run test, execution is replaced with validation only; it does not claim to exercise a solver.

An `xfail` records known unfinished behaviour. The four added real-engine boundary cases are ordinary failures, not xfails. None were hidden to make the full suite appear green.

**14. Exact comparison and test commands**

Run these from the repository directory. Fetch downloads current remote references; it does not merge the branches.

```powershell
git fetch origin
git diff --stat origin/main...HEAD
git diff origin/main...HEAD -- app/domain/validation.py
```

The three dots compare our branch to its common ancestor with main. In this review that ancestor is main itself.

A focused test can be run by naming a file, or one function:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_preference_validation.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_validation.py::test_capacity_errors -q
.\.venv\Scripts\python.exe -m pytest -q
```

The last command runs the whole suite, including unfinished solver/metrics tests. Tests using temporary databases may need the environment's temporary-folder access.

**15. What you should be able to explain**

A useful spoken explanation is: "We extended the starter validator with explicit type, range, reference, and consistency checks. We verify these through unit, form, contract, and database-backed workflow tests. We stop invalid input before a run, distinguish obvious infeasibility from data and database errors, and preserve prior records when related saves fail. Passing validation still does not prove that a feasible assignment exists; the real solver and output checks remain unfinished."

For learning, trace one rejected rank, one optional-project warning, and one failed save from input to result. Be able to explain why `True` is not accepted as a skill level, why two students preferring the same project is allowed, and why a passing validator cannot guarantee a complete allocation.

**16. Every added or changed test function**

The catalogue below covers every test function added or changed relative to main, with its collected example count, input, expected result, and purpose. Shared invalid-value sets are spelled out in the entries where they apply. Existing unchanged tests are not claimed as newly written.

One old form test, `test_skills_outside_catalog_are_ignored`, was replaced by rejection tests because silently dropping an unknown requirement is no longer the working rule.


**tests/test_contract_and_engine.py**

Whole module: 22 collected examples. Added/changed examples explained here: 17.

| Test function | Change | Examples | Input, expected result, and purpose |
| --- | --- | ---: | --- |
| [test_contract_rejects_empty_datasets](../tests/test_contract_and_engine.py#L95) | new | 3 | Tests no students, no projects, and both missing through AssignmentEngine.validate_inputs(). Expects the exact appropriate error list, a ValidationOutcome object, and no mathematical infeasibility claim. |
| [test_contract_reports_identifier_and_parent_errors](../tests/test_contract_and_engine.py#L122) | new | 1 | One request has a preference owned by another student, a requirement owned by another project, duplicate skill ID/name, and a list used as a lock ID. Expects all five structural errors returned through the contract without a crash. |
| [test_contract_returns_preference_diagnostics](../tests/test_contract_and_engine.py#L181) | new | 7 | Seven requests cover a short list, no choices, repeated project, tied rank, boolean rank, rank gap, and unknown project. Expects warnings for the first two and errors for the others, naming S1 and preserving the contract result type. |
| [test_contract_reports_skill_errors_without_claiming_infeasibility](../tests/test_contract_and_engine.py#L210) | new | 1 | Supplies a boolean student level, missing requirement level, string mandatory flag, and repeated requirement. Expects four errors identifying affected owners and no infeasibility reasons. |
| [test_contract_distinguishes_omitted_and_empty_skill_catalogues](../tests/test_contract_and_engine.py#L235) | new | 2 | With student and project references to py, None gives a missing-catalogue warning and remains valid; [] rejects both unknown references. Proves the distinction reaches Team A's interface. |
| [test_convenience_run_preserves_skill_catalogue_policy](../tests/test_contract_and_engine.py#L258) | new | 2 | Calls run_assignment() with None and [] while temporarily replacing execution with the real validator. None must warn and remain valid; [] must reject py. No solutions are produced; this verifies request construction without implementing a solver. |
| [test_contract_rejects_non_integer_capacity](../tests/test_contract_and_engine.py#L283) | new | 1 | Submits max_capacity='2' as a domain value. Expects the contract result to reject it with P1 and the whole-number requirement, without a false shortage claim. |


**tests/test_database_validation.py**

Whole module: 17 collected examples. Added/changed examples explained here: 17.

| Test function | Change | Examples | Input, expected result, and purpose |
| --- | --- | ---: | --- |
| [test_invalid_saved_values_cannot_start_a_mock_run](../tests/test_database_validation.py#L15) | new | 4 | Four examples alter saved SQLite values: profile level 6, requirement level 2.5, preference rank 1.5, and capacity 'many'. Posting a run must record INVALID_INPUT, identify S1/P1 in diagnostics, and store zero solutions. |
| [test_invalid_saved_mandatory_flag_is_not_coerced_to_true](../tests/test_database_validation.py#L41) | new | 1 | Temporarily bypasses the SQLite CHECK constraint to save 'false'. Direct project loading must raise InvalidDatabaseRecords; starting a run must return HTTP 422 with P1/py and save no run. Proves the text cannot silently become True. |
| [test_orphaned_saved_reference_is_identified](../tests/test_database_validation.py#L63) | new | 1 | Temporarily disables foreign-key enforcement to insert a profile referencing ghost. Starting a run must return HTTP 422 identifying the student_skills row and missing skills parent, with no run saved. |
| [test_unavailable_database_at_startup_has_a_useful_page](../tests/test_database_validation.py#L80) | new | 2 | Two examples use a non-SQLite file and a file where the database's parent folder should be. App creation handles each failure; GET / returns the useful HTTP 503 page, not INFEASIBLE, and CSS still loads. |
| [test_locked_database_write_is_reported](../tests/test_database_validation.py#L99) | new | 1 | Holds a real SQLite BEGIN IMMEDIATE writer lock, uses a short timeout, and submits a new skill. Expects HTTP 503 and no skill saved; the test releases the lock in finally. |
| [test_read_only_database_write_is_reported](../tests/test_database_validation.py#L116) | new | 1 | Temporarily injects a real SQLite connection opened with mode=ro. Submitting a skill returns HTTP 503 and leaves the skill catalogue empty. |
| [test_invalid_saved_capacity_does_not_crash_dashboard](../tests/test_database_validation.py#L133) | new | 1 | Stores max_capacity='many' and opens the dashboard. Expects HTTP 422 identifying P1/capacity rather than a Python summation error. |
| [test_invalid_saved_capacity_cannot_crash_the_lock_form](../tests/test_database_validation.py#L144) | new | 1 | Stores max_capacity='many' and posts a fixed assignment. Expects a correction message, final page HTTP 200 after redirect, and no saved lock. |
| [test_failed_student_save_rolls_back_existing_profile](../tests/test_database_validation.py#L159) | new | 1 | Starts with Original and py=2, then tries to save Changed, py=4, and unknown ghost. A real foreign-key error must roll back both name and profile changes. This verifies single-save rollback that already existed on main. |
| [test_failed_run_save_rolls_back_every_related_row](../tests/test_database_validation.py#L174) | new | 1 | Attempts to save a run, solution, and assignment to missing student/project IDs. Expects IntegrityError and no run, solution, or assignment rows left behind; verifies the existing run-save transaction. |
| [test_failed_cohort_replacement_restores_old_data](../tests/test_database_validation.py#L190) | new | 1 | Starts with student OLD. Replacing the cohort with NEW referencing ghost fails after deletion/inserts have begun. OLD must remain, NEW must be absent, and no new project may survive the rollback. |
| [test_unknown_scenario_does_not_clear_existing_inputs](../tests/test_database_validation.py#L206) | new | 1 | Saves S1 and posts /load-scenario/unknown. The request redirects to an explanatory page and S1 remains saved. Catches the old route deleting input before checking the scenario name. |
| [test_failed_mock_run_also_rolls_back_its_new_lock](../tests/test_database_validation.py#L216) | new | 1 | Saves a source solution and installs a SQLite trigger rejecting a new run insert. Lock-and-rerun must return HTTP 503, remove the attempted new lock, and preserve the source run/assignment. Proves the whole mock workflow shares one transaction. |


**tests/test_edge_cases.py**

Whole module: 15 collected examples. Added/changed examples explained here: 1.

| Test function | Change | Examples | Input, expected result, and purpose |
| --- | --- | ---: | --- |
| [test_edge_case_6_unknown_skill_in_entity](../tests/test_edge_cases.py#L178) | changed | 1 | Existing edge-case test now expects fatal errors for the student's quantum_computing and project's cryptography references absent from a supplied catalogue. Previously it expected warnings. It also checks that invalid references are not reported as mathematical infeasibility. |


**tests/test_feasibility_validation.py**

Whole module: 12 collected examples. Added/changed examples explained here: 12.

| Test function | Change | Examples | Input, expected result, and purpose |
| --- | --- | ---: | --- |
| [test_exact_allocation_capacity_deficit_is_explained](../tests/test_feasibility_validation.py#L9) | new | 1 | Two students and one project place must report infeasibility with both quantities in the explanation. |
| [test_minimum_capacity_shortage_is_always_infeasible](../tests/test_feasibility_validation.py#L20) | new | 2 | One student cannot fill minimum 2. Tests both enforce_exact_allocation=True and False; neither option removes required project minima. |
| [test_uncovered_optional_project_can_stay_unused](../tests/test_feasibility_validation.py#L31) | new | 1 | P1 requires Python level 3, nobody qualifies, and P2 has enough room for the student. Expects valid input with a P1-must-remain-unused warning and no infeasibility reason. |
| [test_unavailable_mandatory_skill_is_reported_when_project_must_be_used](../tests/test_feasibility_validation.py#L48) | new | 3 | Three examples force the uncovered Python project to be used through its positive minimum, an existing lock, or total demand. Each must report infeasibility naming P1 and py. |
| [test_optional_unusable_projects_do_not_supply_places](../tests/test_feasibility_validation.py#L70) | new | 1 | Two optional projects have unavailable Python requirements, leaving only one usable place for two students. Expects a usable-capacity shortage even though raw total capacity looks sufficient. |
| [test_locks_can_prevent_mandatory_coverage](../tests/test_feasibility_validation.py#L89) | new | 2 | Two examples make a qualified student unavailable: locked to P2, or unable to join full P1 because its one place is already locked to an unqualified student. Both must report P1's missing Python coverage. |
| [test_one_qualified_member_is_enough_for_team_coverage](../tests/test_feasibility_validation.py#L106) | new | 1 | A two-place project requires Python; S1 qualifies and S2 has no Python. Input passes and S2's profile stays empty, verifying team coverage rather than qualification of every member. |
| [test_uneven_preference_demand_is_valid_input](../tests/test_feasibility_validation.py#L120) | new | 1 | Two students prefer P1 while another project has a place. Expects valid input and no infeasibility reason merely because demand is uneven; does not generate assignments. |


**tests/test_fixed_validation.py**

Whole module: 24 collected examples. Added/changed examples explained here: 24.

| Test function | Change | Examples | Input, expected result, and purpose |
| --- | --- | ---: | --- |
| [test_conflicting_locks_name_both_projects](../tests/test_fixed_validation.py#L9) | new | 1 | S1 is locked to P1 and P2. Expects one conflict error naming S1 and both projects, no infeasibility proof, and no change to the submitted locks. |
| [test_duplicate_lock_is_rejected_without_counting_twice](../tests/test_fixed_validation.py#L22) | new | 1 | The identical S1→P1 lock is supplied twice for a one-place project. Expects a duplicate-input error, not a false claim that two distinct students exceed capacity. |
| [test_unknown_lock_reference_is_rejected](../tests/test_fixed_validation.py#L36) | new | 2 | Two examples use unknown student ghost and unknown project ghost. Each must return the affected unknown reference and no infeasibility claim. |
| [test_unique_locks_exceeding_capacity_are_infeasible](../tests/test_fixed_validation.py#L46) | new | 1 | Two distinct valid students are locked to P1 with maximum 1. Expects an infeasibility reason including P1, count 2, and capacity 1. |
| [test_supported_statuses_are_active_locks](../tests/test_fixed_validation.py#L59) | new | 3 | Tests APPROVED, MANDATORY, and CONDITIONAL at capacity equality. All are accepted as active locks under the current branch policy. |
| [test_unsupported_lock_status_is_rejected](../tests/test_fixed_validation.py#L69) | new | 9 | Rejects None, empty text, lowercase approved, PENDING, REJECTED, True, 1, [], and {} with a useful unsupported-status message naming S1. |
| [test_invalid_lock_ids_do_not_crash_focused_validation](../tests/test_fixed_validation.py#L79) | new | 1 | A list student ID and missing project ID must produce two text-type errors before set/dictionary lookups. |
| [test_contract_rejects_bad_lock_status](../tests/test_fixed_validation.py#L89) | new | 1 | Passes PENDING through AssignmentEngine.validate_inputs() and expects an unsupported-status error. Shows the focused rule is also applied through the public interface. |
| [test_focused_lock_validation_rejects_bad_saved_capacity](../tests/test_fixed_validation.py#L105) | new | 5 | Tests None, numeric text '1', 1.5, zero, and True as a capacity passed to the standalone lock validator. Each must reject P1's capacity without a crash or false infeasibility proof. |


**tests/test_forms.py**

Whole module: 40 collected examples. Added/changed examples explained here: 23.

| Test function | Change | Examples | Input, expected result, and purpose |
| --- | --- | ---: | --- |
| [test_skills_outside_catalog_are_rejected](../tests/test_forms.py#L66) | new | 2 | Two examples post unknown req_level_r and req_mand_r fields. ProjectForm must return None with an unknown-r error, replacing the old silent-ignore expectation. |
| [test_project_form_rejects_unsupported_mandatory_flags](../tests/test_forms.py#L114) | new | 6 | Rejects checkbox text 'false', 'true', '0', '2', 'yes', and 'off'. None may be interpreted as checked merely because it is nonempty. |
| [test_project_form_parses_supported_checkbox_values](../tests/test_forms.py#L123) | new | 3 | Checks '1'→True, 'on'→True, and empty text→False in the parsed project requirement. |
| [test_student_skill_form_rejects_invalid_levels](../tests/test_forms.py#L134) | new | 7 | Rejects '-1', '6', '1.5', '2.0', 'bad', 'true', and 'inf'. The form returns None and a py-level error. |
| [test_student_skill_form_omits_zero_or_blank_levels](../tests/test_forms.py#L143) | new | 3 | Three examples omit SQL through '0', empty text, or whitespace while parsing ' 5 ' for Python. Expects exactly {'py': 5} and no errors. |
| [test_student_skill_form_rejects_unknown_skill](../tests/test_forms.py#L153) | new | 1 | Posts skill_ghost=3 against the known catalogue. Expects None and an unknown-skill error. |
| [test_student_skill_form_collects_errors_and_can_be_rechecked](../tests/test_forms.py#L161) | new | 1 | Initially py='bad' and sql='6' must give two errors. Correcting the same form data to levels 1 and 5 must produce a valid dictionary and clear the old errors. |

Replaced older expectation: `test_skills_outside_catalog_are_ignored`. Unknown requirement fields now require correction instead of being discarded.


**tests/test_identifier_validation.py**

Whole module: 58 collected examples. Added/changed examples explained here: 58.

| Test function | Change | Examples | Input, expected result, and purpose |
| --- | --- | ---: | --- |
| [test_invalid_catalogue_identifier_is_rejected](../tests/test_identifier_validation.py#L25) | new | 30 | Runs 10 bad IDs against each of student, project, and skill: empty text, whitespace-only text, None, 7, 1.5, True, [], {}, leading space, and trailing tab. All 30 examples return one useful identifier error before feasibility calculations. |
| [test_invalid_reference_identifiers_are_reported_together](../tests/test_identifier_validation.py#L50) | new | 6 | Six invalid values (None, 7, True, empty text, whitespace, padded text) are placed in seven reference fields: preference student/project, profile skill key, requirement project/skill, and fixed student/project. Expects all seven field errors together for each value. |
| [test_unhashable_reference_identifiers_do_not_crash](../tests/test_identifier_validation.py#L91) | new | 2 | Uses [] and {} in six nested reference fields, excluding profile dictionary keys because Python itself cannot create those keys. Expects six text errors and no set/dictionary lookup crash. |
| [test_duplicate_skill_identifiers_are_rejected](../tests/test_identifier_validation.py#L119) | new | 1 | Two skill records have ID py but different names. Expects the duplicate-ID error; different names cannot make one shared ID unique. |
| [test_duplicate_skill_names_are_rejected](../tests/test_identifier_validation.py#L144) | new | 5 | Five pairs test identical Python names, upper/lower case, leading/trailing spaces on either record, and Straße/STRASSE. Expects one duplicate-name error naming both skill IDs. |
| [test_skill_name_must_be_nonempty_text](../tests/test_identifier_validation.py#L162) | new | 4 | Names None, 7, empty text, and whitespace must give a clear nonempty-text error before casefold is used. |
| [test_preference_must_belong_to_containing_student](../tests/test_identifier_validation.py#L175) | new | 3 | A preference inside S1 uses S2, nonexistent S99, or lowercase s1 as its owner. Each is rejected even when another referenced student exists. |
| [test_requirement_must_belong_to_containing_project](../tests/test_identifier_validation.py#L196) | new | 3 | A requirement inside P1 uses P2, nonexistent P99, or lowercase p1 as its owner. Each is rejected even when another referenced project exists. |
| [test_identifiers_are_case_sensitive_and_display_names_need_not_be_unique](../tests/test_identifier_validation.py#L216) | new | 1 | Builds distinct S1/s1, P1/p1, and py/PY records with exact matching references and duplicate student display names/project titles. The cohort must pass unchanged with no warnings. This concerns domain validation; it does not assert every UI name policy. |
| [test_identifier_may_be_numeric_text_and_reused_in_another_catalogue](../tests/test_identifier_validation.py#L254) | new | 1 | Student, project, and skill each use the text ID '7'. Expects valid input because text is allowed and uniqueness is within each catalogue. |
| [test_unmatched_reference_case_is_explained_without_changing_ids](../tests/test_identifier_validation.py#L266) | new | 1 | Uses PY instead of known py, p1 instead of P1, and s1 instead of S1 in references. Expects five errors explaining case sensitivity and checks that the original objects remain unchanged. |
| [test_bad_identifier_stops_feasibility_checks](../tests/test_identifier_validation.py#L294) | new | 1 | Two S1 records and one place would look like a shortage if counted blindly. Expects only the duplicate-ID error and no mathematical infeasibility claim. |


**tests/test_preference_validation.py**

Whole module: 35 collected examples. Added/changed examples explained here: 35.

| Test function | Change | Examples | Input, expected result, and purpose |
| --- | --- | ---: | --- |
| [test_short_preference_list_warns](../tests/test_preference_validation.py#L18) | new | 2 | One and two distinct ranked projects are valid input but produce a warning naming S1 and the expected minimum of three. Submitted preferences remain unchanged. |
| [test_small_project_catalogue_is_explained](../tests/test_preference_validation.py#L39) | new | 2 | With only one or two projects offered, warns that ranking three projects is impossible while leaving otherwise valid input accepted. |
| [test_no_preferences_warns_about_unranked_assignment](../tests/test_preference_validation.py#L59) | new | 1 | An empty list remains empty and valid, with a warning naming S1, at least three expected choices, and possible unranked assignment. No choices are invented. |
| [test_three_or_more_valid_preferences_need_no_warning](../tests/test_preference_validation.py#L76) | new | 2 | Three and four valid distinct ranked choices both pass without warnings; the rule is not an upper limit of three. |
| [test_bad_entries_do_not_count_as_three_choices](../tests/test_preference_validation.py#L94) | new | 2 | A third entry repeats P1 or refers to P99. Both are rejected, and the short-list warning counts only the two distinct available projects. |
| [test_repeated_project_is_rejected](../tests/test_preference_validation.py#L111) | new | 1 | S1 ranks P1 at both positions 1 and 2. Expects an error naming S1/P1, no mathematical infeasibility claim, and unchanged input. |
| [test_tied_ranks_within_one_student_are_rejected](../tests/test_preference_validation.py#L130) | new | 2 | Two different projects share rank 1 or share rank 2. Each example returns a tied-rank error; this is different from different students preferring the same project. |
| [test_students_can_compete_for_the_same_first_choice](../tests/test_preference_validation.py#L149) | new | 1 | Two students both rank one-place P1 first and have other choices available. Input passes without warnings/errors. The test does not decide which student receives P1. |
| [test_preference_rank_must_be_a_positive_integer](../tests/test_preference_validation.py#L192) | new | 15 | Rejects 0, -1, 1.5, 2.0, '1', 'bad', empty text, None, True, False, NaN, positive/negative infinity, [], and {}. Each gives one useful rank error and no crash or mathematical infeasibility claim. |
| [test_multiple_preference_errors_are_reported_together](../tests/test_preference_validation.py#L208) | new | 1 | One list contains a list-valued rank, duplicate P2, tied rank 1, and unknown P99. Expects all four errors so one malformed value does not hide other corrections. |
| [test_rank_gaps_are_rejected_without_renumbering](../tests/test_preference_validation.py#L232) | new | 4 | Rejects ranks [1,3,7], [2], [2,3,4], and [1,2,10**12]. Expects a single no-gaps error and verifies the original ranks are unchanged. |
| [test_valid_ranks_need_not_arrive_in_sorted_order](../tests/test_preference_validation.py#L249) | new | 1 | Preference records arrive as ranks 3,1,2. They pass because the rank set is complete, and the input list remains in that order. |
| [test_unknown_preference_project_identifies_student_and_project](../tests/test_preference_validation.py#L265) | new | 1 | S1 ranks missing P99. The error must name both IDs and the input reference must remain P99. |


**tests/test_run_validation.py**

Whole module: 36 collected examples. Added/changed examples explained here: 36.

| Test function | Change | Examples | Input, expected result, and purpose |
| --- | --- | ---: | --- |
| [test_dashboard_run_settings_are_accepted](../tests/test_run_validation.py#L13) | new | 6 | Tests all three strategy names with requested counts 1 and 4, giving six combinations. Validation accepts the dashboard's supported boundaries; this does not exercise strategy algorithms. |
| [test_unknown_run_strategy_is_rejected](../tests/test_run_validation.py#L25) | new | 8 | Rejects None, empty text, lowercase preference, UNKNOWN, True, 1, [], and {} with a strategy error and no mathematical infeasibility claim. |
| [test_invalid_alternative_count_is_rejected](../tests/test_run_validation.py#L39) | new | 15 | Rejects None, 0, -1, 5, 10**12, 1.5, 2.0, '3', empty text, True, False, NaN, infinity, [], and {}. Expects the 1-to-4 whole-number error without false infeasibility. |
| [test_run_form_rejects_bad_count](../tests/test_run_validation.py#L53) | new | 6 | Posts empty text, 'bad', '2.0', 'true', '0', and '5'. The form returns None and error messages instead of crashing or starting a run. |
| [test_run_form_parses_text_and_uses_default_strategy](../tests/test_run_validation.py#L60) | new | 1 | Parses ' 3 ' into integer 3 and uses PREFERENCE when no strategy is supplied. Expects the tuple ('PREFERENCE', 3) with no form errors. |


**tests/test_skill_validation.py**

Whole module: 67 collected examples. Added/changed examples explained here: 67.

| Test function | Change | Examples | Input, expected result, and purpose |
| --- | --- | ---: | --- |
| [test_missing_student_skill_is_level_zero](../tests/test_skill_validation.py#L31) | new | 2 | Profiles {} and {'sql': 3} omit py for an optional Python requirement. Input passes, get_skill_level('py') returns 0, and the original profile dictionary remains unchanged. |
| [test_missing_skill_does_not_relax_a_mandatory_requirement](../tests/test_skill_validation.py#L49) | new | 1 | P1 must be used and requires Python, but the only student has no skills. Expects missing mandatory coverage, showing omitted skills do not waive hard requirements. |
| [test_student_skill_level_must_be_an_integer_from_one_to_five](../tests/test_skill_validation.py#L65) | new | 16 | Rejects 16 stored profile values: 0, -1, 6, 1.5, 2.0, '3', 'bad', empty text, None, True, False, NaN, positive/negative infinity, [], and {}. Expects one student/skill error before mandatory matching. |
| [test_requirement_level_must_be_an_integer_from_one_to_five](../tests/test_skill_validation.py#L83) | new | 16 | Applies the same 16 invalid values to a project's minimum skill level while its student has level 5. Expects one project/skill input error, not an invalid comparison or false coverage shortage. |
| [test_skill_level_boundaries_and_boolean_flags_are_valid](../tests/test_skill_validation.py#L104) | new | 4 | Combines level 1 or 5 with mandatory False or True, giving four examples. Matching student/project levels and real flags must pass. |
| [test_skill_reference_checks_distinguish_omitted_and_empty_catalogues](../tests/test_skill_validation.py#L122) | new | 6 | For student and project references, tests None, [], and a catalogue containing only py while the records use ghost. None warns and remains valid; supplied catalogues reject unknown references. Six examples verify both owners. |
| [test_no_catalogue_is_needed_when_no_skills_are_used](../tests/test_skill_validation.py#L150) | new | 2 | With no profile skills or project requirements, None and [] both pass without an omitted-catalogue warning. |
| [test_project_without_requirements_has_full_skill_fit](../tests/test_skill_validation.py#L161) | new | 2 | An empty profile and a profile containing Python level 5 both receive exactly (1.0, []) for a project with no requirements. Does not test nonempty-requirement scoring. |
| [test_repeated_requirements_are_rejected](../tests/test_skill_validation.py#L170) | new | 3 | The second py requirement is identical, has a different level, or has a different mandatory flag. All three are rejected with one duplicate-requirement error, without altering the list. |
| [test_mandatory_skill_flag_must_be_a_boolean](../tests/test_skill_validation.py#L194) | new | 14 | Rejects None, 0, 1, -1, 2, 'true', 'false', '0', '1', empty text, [], {}, 0.0, and 1.0 as domain flags. Expects one flag error before unavailable-coverage reasoning. |
| [test_skill_errors_are_reported_together_before_mandatory_matching](../tests/test_skill_validation.py#L212) | new | 1 | Combines text student level, missing requirement level, string mandatory flag, and repeated requirement. Expects all four errors and no premature mathematical infeasibility claim. |


**tests/test_solvers.py**

Whole module: 8 collected examples. Added/changed examples explained here: 4.

| Test function | Change | Examples | Input, expected result, and purpose |
| --- | --- | ---: | --- |
| [test_real_engine_accepts_capacity_boundaries](../tests/test_solvers.py#L23) | new | 4 | Four ordinary failing examples require actual complete assignments at minimum zero, exactly the minimum, exactly the maximum, and equal bounds. All students are locked to P1, making expected output explicit; the zero-minimum case also has an unused optional project. Each currently stops at execute_run's NotImplementedError before output assertions. |


**tests/test_validation.py**

Whole module: 42 collected examples. Added/changed examples explained here: 38.

| Test function | Change | Examples | Input, expected result, and purpose |
| --- | --- | ---: | --- |
| [test_empty_cohort_validation](../tests/test_validation.py#L26) | changed | 1 | Strengthens the existing test to require exactly the two empty-list errors and no shortage/infeasibility reasons. Both missing lists must be reported before other checks. |
| [test_no_students_is_rejected](../tests/test_validation.py#L36) | new | 1 | An empty student list with a project requiring minimum 1 must produce only the empty-cohort input error, not a misleading project-demand calculation. |
| [test_no_projects_is_rejected](../tests/test_validation.py#L49) | new | 1 | One student with no projects must produce only the empty-catalogue error, not a shortage against a meaningless empty problem. |
| [test_capacity_errors](../tests/test_validation.py#L76) | changed | 1 | Strengthens the existing minimum-5/maximum-2 case: the error must name P1 and both bounds, and must not add an infeasibility reason from those invalid numbers. |
| [test_minimum_capacity_must_be_an_integer](../tests/test_validation.py#L98) | new | 12 | For the minimum field, rejects None, empty text, spaces, '2', 'two', 1.5, 2.0, True, False, NaN, infinity, and negative infinity. Expects a P1/whole-number error before capacity arithmetic. |
| [test_maximum_capacity_must_be_an_integer](../tests/test_validation.py#L121) | new | 12 | Applies the same 12 invalid values to maximum capacity. Each must reject clearly without a crash or mathematical shortage claim. |
| [test_capacity_type_errors_are_reported_together](../tests/test_validation.py#L143) | new | 1 | Two projects each have invalid minimum and maximum types while a third is valid. Expects all four type errors and no infeasibility reasoning from partial totals. |
| [test_negative_minimum_capacity_is_rejected](../tests/test_validation.py#L184) | new | 2 | Tests minimum -1 and -2 with an otherwise valid maximum. Expects an input error identifying P1 and no mathematical infeasibility claim. |
| [test_non_positive_maximum_capacity_is_rejected](../tests/test_validation.py#L206) | new | 2 | Tests maximum 0 and -1. Each is invalid input and must not be used as if it were a valid number of available places. |
| [test_invalid_capacity_ranges_are_not_used_to_prove_infeasibility](../tests/test_validation.py#L229) | new | 1 | P1 has min 5/max 2 and P2 has min -1/max 0. Expects exactly the three range errors, both project IDs represented, and no aggregate shortage proof using invalid bounds. |
| [test_zero_minimum_capacity_is_allowed](../tests/test_validation.py#L247) | new | 1 | One student and min 0/max 1 must pass domain validation. This establishes input acceptance only. |
| [test_cohort_at_minimum_capacity_is_allowed](../tests/test_validation.py#L262) | new | 1 | Two students with min 2/max 3 must pass input validation, showing equality at the minimum is allowed. |
| [test_cohort_at_maximum_capacity_is_allowed](../tests/test_validation.py#L280) | new | 1 | Two students locked to P1 with min 1/max 2 must pass input validation, showing equality at the maximum is allowed. |
| [test_equal_minimum_and_maximum_capacity_is_allowed](../tests/test_validation.py#L304) | new | 1 | Two students with min=max=2 must pass input validation, showing an exact required headcount is valid. |


**tests/test_visualization_component.py**

Whole module: 67 collected examples. Added/changed examples explained here: 32.

| Test function | Change | Examples | Input, expected result, and purpose |
| --- | --- | ---: | --- |
| [test_ambiguous_project_case_requires_exact_id](../tests/test_visualization_component.py#L179) | new | 1 | Saves ProjectA and projecta. Posting PROJECTA must reject student creation with an exact-spelling message. Posting both exact IDs must then save two distinct preferences successfully. |
| [test_repeated_preference_is_not_silently_saved](../tests/test_visualization_component.py#L209) | new | 4 | Combines create/update with 'P1, P1' and 'P1, p1' when only P1 matches, giving four examples. Each reports repetition; create saves nothing and update preserves the original name and P2 preference. |
| [test_bad_student_skills_leave_saved_records_unchanged](../tests/test_visualization_component.py#L246) | new | 6 | Combines create/update with py=6, py='bad', and ghost=3, giving six examples. Invalid creation leaves no student; invalid editing preserves the old name and py=2 profile. |
| [test_bad_project_skill_fields_leave_saved_records_unchanged](../tests/test_visualization_component.py#L277) | new | 4 | Combines create/update with mandatory text 'false' and an unknown ghost requirement, giving four examples. Creation saves nothing; editing preserves original title and requirements. |
| [test_invalid_lock_form_preserves_existing_lock](../tests/test_visualization_component.py#L312) | new | 6 | Starts with S1→P1 and posts six bad additions: duplicate, conflicting project for S1, second student exceeding P1 capacity, unknown student, unknown project, or PENDING status. Each must leave exactly the original lock and show no creation-success message. |
| [test_invalid_run_settings_do_not_start_a_mock_run](../tests/test_visualization_component.py#L338) | new | 5 | After loading valid sample data, posts missing settings, count 'bad', '0', '5', or unknown strategy. Expects explanatory pages, no success message, and no run records. |
| [test_invalid_cohort_is_recorded_without_mock_solutions](../tests/test_visualization_component.py#L349) | new | 1 | Posts a valid count with a saved project but no students. Expects one INVALID_INPUT audit run, the empty-cohort diagnostic, no solutions, and no mock-demonstration message. |
| [test_lock_and_rerun_validates_before_saving](../tests/test_visualization_component.py#L365) | new | 4 | Four examples cover a valid source pair, a conflicting existing lock, a forged pair absent from the source solution, and an unknown source solution. Only the valid case creates a second run/new lock; rejected cases preserve existing runs and locks. |
| [test_create_skill_rejects_name_matching_padded_existing_name](../tests/test_visualization_component.py#L494) | new | 1 | Saves a skill named ' Python ' and submits a different ID with name PYTHON. Expects a duplicate-name message, no second skill, and no silent renaming of the existing record. |


The 41 completed checklist items group related behaviours; they are not a count of individual tests. The 18 open items include real solver/output verification and historical snapshots. The mathematical model and method justification still need separate work for the Week 1 milestone.

