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

- Mark `[x]` when the working response is agreed, implemented, and tested.
- Keep unfinished output checks and expected failures (`xfail`) open.
- Record rules and short test evidence here. Detailed history stays in Git.
- Implemented branch policies still need normal team review; they do not
  establish instructor approval of a solver or scoring method.

## Where we work

| Area | Main implementation | Main tests |
| --- | --- | --- |
| Input checks and obvious feasibility problems | [app/domain/validation.py](../app/domain/validation.py), especially `validate_cohort()` | [tests/test_validation.py](../tests/test_validation.py), [tests/test_identifier_validation.py](../tests/test_identifier_validation.py), [tests/test_preference_validation.py](../tests/test_preference_validation.py), and [tests/test_edge_cases.py](../tests/test_edge_cases.py) |
| Validation through the interface Team A uses | `AssignmentEngine.validate_inputs()` in [app/engine/solvers.py](../app/engine/solvers.py) | [tests/test_contract_and_engine.py](../tests/test_contract_and_engine.py) |
| Producing feasible, distinct assignments | `execute_run()` and the strategies in `app/engine/solvers.py` | [tests/test_solvers.py](../tests/test_solvers.py) and `tests/test_edge_cases.py` |
| Checking and comparing result measures | [app/engine/metrics.py](../app/engine/metrics.py) | [tests/test_metrics.py](../tests/test_metrics.py) |
| Saving and loading safely | [app/persistence/database.py](../app/persistence/database.py), [repositories.py](../app/persistence/repositories.py), and [schema.sql](../app/persistence/schema.sql) | [tests/test_persistence.py](../tests/test_persistence.py) and integration tests |
| Showing understandable messages | Team A's routes and templates, using the engine's returned errors and warnings | UI and integration tests with Team A |

Start with the input checks this week. Plan the solver, result, and database
cases now; implement them alongside the relevant component. Shared domain,
database, and contract changes need coordination with Team A.

## Student, project, and skill identifiers

- [x] ID-01 **No students** - reject the empty cohort before capacity calculations.
- [x] ID-02 **No projects** - reject the empty catalogue before capacity calculations. If both lists are empty, report both errors.
- [x] ID-03 **Blank identifiers** - reject empty or whitespace-only IDs, including IDs in preferences, requirements, student skills, and fixed assignments.
- [x] ID-04 **Identifiers of the wrong type** - reject non-text IDs before lookups. Text `"7"` is valid; number `7` is not.
- [x] ID-05 **Duplicate identifiers** - reject repeated IDs within each catalogue. Different IDs may have the same display name or title.
- [x] ID-06 **Duplicate skill names** - reject names equal after ignoring surrounding spaces and letter case. Names must be nonempty text.
- [x] ID-07 **A record refers to the wrong parent** - reject preferences or requirements whose owner ID differs from the containing student or project.
- [x] ID-08 **Differences in case or spaces** - stored IDs are case-sensitive and cannot have surrounding whitespace. Explain unmatched references without changing them.

Forms keep their existing parsing: trim entry spaces and lowercase new skill
IDs. Preference forms use exact IDs first, accepting a case-insensitive
match only when unique. Ambiguous matches are rejected. SQLite and the
engine keep `P1` and `p1` distinct. Skill-name comparison is stricter than
SQLite's exact `UNIQUE` rule. The existing student form's separate restriction
on duplicate display names is unchanged.

Evidence: `tests/test_identifier_validation.py` (58 examples), empty-input
checks in `tests/test_validation.py`, and contract/form checks below.

| Cases | Main tests | Verified response |
| --- | --- | --- |
| ID-01/02 | `test_no_students_is_rejected`, `test_no_projects_is_rejected`, `test_contract_rejects_empty_datasets` | Missing data give clear errors, without capacity-shortage claims. |
| ID-03/04 | `test_invalid_catalogue_identifier_is_rejected`, `test_invalid_reference_identifiers_are_reported_together`, `test_unhashable_reference_identifiers_do_not_crash` | Blank, non-text, and padded IDs return field errors without crashing. |
| ID-05/06 | `test_duplicate_identifiers`, `test_duplicate_skill_identifiers_are_rejected`, `test_duplicate_skill_names_are_rejected`, `test_skill_name_must_be_nonempty_text` | Duplicate IDs/names and unusable names are rejected. |
| ID-07 | `test_preference_must_belong_to_containing_student`, `test_requirement_must_belong_to_containing_project` | Wrong owners are identified, including existing IDs and case differences. |
| ID-08 | `test_identifiers_are_case_sensitive_and_display_names_need_not_be_unique`, `test_unmatched_reference_case_is_explained_without_changing_ids`, `test_ambiguous_project_case_requires_exact_id` | Exact case-distinct references survive validation and persistence; ambiguous form input is rejected. |
| Interface/forms | `test_contract_reports_identifier_and_parent_errors`, `test_create_skill_rejects_name_matching_padded_existing_name` | Errors reach Team A; rejected duplicate names are not saved. |

Identifier and skill-name errors stop validation before feasibility checks.
The repositories' direct `save()` methods have not gained these checks;
loading invalid saved records remains DB-01 work. Skill references follow
SKILL-04/05 below.

## Project preferences supplied by students

Working branch policies: short/empty lists warn, duplicate projects and tied
ranks are rejected to match SQLite's unique preference rules.
The user confirmed rank-gap rejection on 2026-10-20. Other policies await
team review; unranked scoring and assignment tie-breakers remain open.

- [x] PREF-01 **Incomplete project preferences** - warn when fewer than three distinct available projects have valid ranks. Also warn when fewer than three projects are offered.
- [x] PREF-02 **No preferences at all** - warn that the student may receive an unranked project. Do not invent preferences or reject solely for this reason. Scoring remains OUT-05/12 work.
- [x] PREF-03 **The same project appears twice** - reject and ask for a correction. Forms reject repeated IDs and aliases before saving, instead of silently removing duplicates.
- [x] PREF-04 **One student gives two projects the same rank** - reject tied ranks until the app and database can represent them consistently.
- [ ] PREF-05 **Several students want the same project** - input validation accepts this as normal competition (verified). Solver capacity enforcement and explanation remain unfinished; see OUT-04 and `test_edge_case_2_tied_preferences_across_students` (`xfail`).
- [x] PREF-06 **Invalid preference ranks** - reject zero, negatives, fractions, floats, text, missing values, booleans, and non-finite numbers. Ranks must be positive whole numbers.
- [x] PREF-07 **Gaps in the ranks** - reject gaps or a first rank other than 1. Require ranks 1 through N, where N is the number of choices. Input list order may differ; do not renumber or reorder submitted records.
- [x] PREF-08 **Unknown project** - reject and identify the affected student and project.

Evidence: `tests/test_preference_validation.py` (35 examples), plus contract
and form tests. All use synthetic records.

| Cases | Main tests | Example and expected result |
| --- | --- | --- |
| PREF-01 | `test_short_preference_list_warns`, `test_small_project_catalogue_is_explained`, `test_three_or_more_valid_preferences_need_no_warning`, `test_bad_entries_do_not_count_as_three_choices` | One/two choices warn; three/four valid choices pass without preference warnings. Duplicates and unknown projects do not inflate the count. |
| PREF-02 | `test_no_preferences_warns_about_unranked_assignment` | Empty preferences remain empty; return a warning mentioning an unranked project. |
| PREF-03/04 | `test_repeated_project_is_rejected`, `test_tied_ranks_within_one_student_are_rejected` | Repeated project IDs and tied ranks return errors for that student. |
| PREF-05 input | `test_students_can_compete_for_the_same_first_choice` | Two students ranking a one-place project first are valid input when other places exist. No assignments are produced by this test. |
| PREF-06 | `test_preference_rank_must_be_a_positive_integer`, `test_multiple_preference_errors_are_reported_together` | Fifteen bad rank values are rejected without crashes; several errors are returned together. |
| PREF-07 | `test_rank_gaps_are_rejected_without_renumbering`, `test_valid_ranks_need_not_arrive_in_sorted_order` | Reject 1/3/7 and a huge rank; accept unsorted records carrying ranks 1/2/3, leaving records unchanged. |
| PREF-08 | `test_unknown_preference_project_identifies_student_and_project` | Return an error naming S1 and unknown project P99. |
| Interface/forms | `test_contract_returns_preference_diagnostics` (7 examples), `test_repeated_preference_is_not_silently_saved` (4 examples) | Team A receives errors/warnings. Rejected create/edit forms save nothing or preserve the previous student record. |

## Student skills and project requirements

- [x] SKILL-01 **Missing skills from a student's profile** - accept an omitted skill as level 0, without adding it to the profile. Mandatory coverage still applies; missing skills alone do not prove that a student can be assigned.
- [x] SKILL-02 **Invalid student skill levels** - stored levels must be integers from 1 to 5. Reject missing values, text, floats, booleans, and values outside the range. A missing skill is an omitted dictionary entry, not a stored zero.
- [x] SKILL-03 **Invalid project requirement levels** - require integers from 1 to 5; reject other values before mandatory matching.
- [x] SKILL-04 **Unknown skills** - reject profile and requirement references missing from a supplied catalogue, naming the student/project and skill. Forms also reject unknown skill fields instead of silently dropping them.
- [x] SKILL-05 **Absent or empty catalogue** - omitted `None` preserves the optional contract: warn when references cannot be checked. An explicit empty list rejects all skill references. Either is accepted without a catalogue warning when no skills are used.
- [x] SKILL-06 **No project skill requirements** - accept the project and return skill fit `1.0` with no unmet skills. Scoring nonempty requirements remains unfinished in `metrics.py`.
- [x] SKILL-07 **Repeated or conflicting requirements** - reject both identical and conflicting duplicates for correction; leave the submitted list unchanged.
- [x] SKILL-08 **Invalid mandatory flag** - domain objects require real `True`/`False` values. Forms accept only an unchecked box (missing/empty) or checked values `1`/`on`; reject other text, including `"false"`.

These are implemented branch rules for team review. `StudentSkillsForm`
parses student fields for both create and edit routes. Form zero/blank levels
mean an omitted skill or optional requirement; a mandatory requirement still
needs a level. Domain checks collect errors before using skill data for
mandatory matching. Independent capacity checks still run. No general
scoring formula or mandatory team-coverage policy is introduced here.

Evidence: `tests/test_skill_validation.py` (67 examples), plus form, contract,
and database-backed web tests. All examples use synthetic records.

| Cases | Main tests | Verified response |
| --- | --- | --- |
| SKILL-01 | `test_missing_student_skill_is_level_zero`, `test_missing_skill_does_not_relax_a_mandatory_requirement` | Missing skills remain absent/level 0; unavailable required coverage is still reported. |
| SKILL-02/03 | `test_student_skill_level_must_be_an_integer_from_one_to_five`, `test_requirement_level_must_be_an_integer_from_one_to_five`, `test_skill_level_boundaries_and_boolean_flags_are_valid` | Reject 16 bad values per level field; accept levels 1 and 5. |
| SKILL-04/05 | `test_skill_reference_checks_distinguish_omitted_and_empty_catalogues`, `test_no_catalogue_is_needed_when_no_skills_are_used` | Omitted catalogue warns for references; supplied catalogues reject unknown IDs, including when empty. |
| SKILL-06 | `test_project_without_requirements_has_full_skill_fit` | Empty and populated profiles both receive `(1.0, [])` for a project with no requirements. |
| SKILL-07 | `test_repeated_requirements_are_rejected` | Identical rows, different levels, and conflicting flags all give errors without changing the list. |
| SKILL-08 | `test_mandatory_skill_flag_must_be_a_boolean`, `test_project_form_rejects_unsupported_mandatory_flags` | Reject non-boolean domain flags and unsupported checkbox text; do not treat `"false"` as true. |
| Interface/forms | `test_contract_reports_skill_errors_without_claiming_infeasibility`, `test_bad_student_skills_leave_saved_records_unchanged`, `test_bad_project_skill_fields_leave_saved_records_unchanged` | Errors reach Team A; rejected create/edit forms preserve saved data. |

## Project capacities

- [x] CAP-01 **Missing or non-integer capacities** - reject before calculations. Include missing/blank values, numeric text, fractions, booleans, and non-finite numbers. Forms may parse text into integers first.
- [x] CAP-02 **Negative minimum or non-positive maximum** - reject. Minimum must be at least 0 and maximum at least 1, matching SQLite.
- [x] CAP-03 **Minimum exceeds maximum** - reject and identify the project and bounds.
- [ ] CAP-04 **Capacity exactly at a boundary** - valid input bounds pass, including minimum 0 and equal bounds. Four real-engine output tests still fail because `execute_run()` is unfinished; see OUT-04.

Evidence: capacity cases in `tests/test_validation.py`, the contract test,
and `tests/test_solvers.py`.

| Cases | Main tests | Verified response |
| --- | --- | --- |
| CAP-01 | `test_minimum_capacity_must_be_an_integer`, `test_maximum_capacity_must_be_an_integer`, `test_capacity_type_errors_are_reported_together`, `test_contract_rejects_non_integer_capacity` | Reject 12 invalid values per field; collect several field errors and return them through the contract without false shortage claims. |
| CAP-02/03 | `test_negative_minimum_capacity_is_rejected`, `test_non_positive_maximum_capacity_is_rejected`, `test_capacity_errors` | Invalid ranges are rejected with the affected project/bounds. |
| CAP-04 input | `test_zero_minimum_capacity_is_allowed`, `test_cohort_at_minimum_capacity_is_allowed`, `test_cohort_at_maximum_capacity_is_allowed`, `test_equal_minimum_and_maximum_capacity_is_allowed` | All four input boundaries pass. |
| CAP-04 output | `test_real_engine_accepts_capacity_boundaries` | Four failures at `NotImplementedError`; actual assignment assertions are not reached. |

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

## Verification and next steps

On 2026-10-20, the focused checks returned **315 passed, 4 xfailed**:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_skill_validation.py tests/test_forms.py tests/test_validation.py tests/test_identifier_validation.py tests/test_preference_validation.py tests/test_contract_and_engine.py tests/test_visualization_component.py tests/test_persistence.py tests/test_metrics.py -q --tb=short -p no:cacheprovider
```

Full suite: **332 passed, 12 xfailed, 4 failed**:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=short -p no:cacheprovider
```

The four failures are the existing CAP-04 real-engine boundary tests;
`execute_run()` is not implemented. No new full-suite failures. The branch
still does not meet the passing-suite requirement for merging. Database
checks ran with access to pytest's separate temporary databases.

Next: FIX-01 to FIX-05 and the open feasibility/solver checks. Shared form
changes need the normal cross-team PR review. No contract, model, schema,
or solver method changed. General scoring remains unfinished; only the
documented no-requirement skill-fit case is implemented.

AI assisted with implementation, synthetic tests, and this checklist on
2026-10-20. Preference work added 35 domain, 7 contract, and 4 form examples.
Earlier detailed test walkthroughs were shortened into the tables above;
their history remains in Git. Student understanding is not yet verified.
Skill work added 67 domain/score examples, 3 contract examples, 10 web examples,
and 21 form examples, and replaced the old ignored-unknown-field form test
with two rejection examples. Existing unknown-skill tests now expect errors
instead of warnings. AI assisted with these changes and the short evidence table.
