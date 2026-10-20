# Input and output validation checklist

This is Team B's working list of things that could go wrong with the data,
the assignment results, or saving and loading them. It covers the situations
in the course brief and additional examples found while reviewing the starter.

The responses below are **proposals for team discussion**, unless described
as an existing rule. A warning means the application may continue while
explaining the problem. Rejecting input means the data must be corrected.
Infeasibility means the agreed hard constraints cannot all be satisfied.
A database failure means an operation failed; it does not prove infeasibility.

Current scope (confirmed by the user on 2026-10-20): Week 1 input validation
and feasibility checks. The instructor has not approved an assignment method.
Solver-dependent output and comparison cases stay open for later work.

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
- [x] SKILL-05 **Absent or empty catalogue** - omitted `None` preserves the optional contract: warn when references cannot be checked. An explicit empty list rejects all skill references. Either is accepted without a catalogue warning when no skills are used. The convenience `run_assignment()` method preserves this distinction too.
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
Two convenience-API regression examples use the real validator with a test
replacement for execution; no solver or assignments are involved.

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

- [x] FIX-01 **One student is fixed to different projects** - reject and name both projects. Release an existing lock explicitly before choosing another project.
- [x] FIX-02 **The same fixed assignment appears twice** - reject the duplicate before capacity counting; do not count one student twice.
- [x] FIX-03 **Unknown student or project** - reject and identify the missing reference, using exact case-sensitive IDs.
- [x] FIX-04 **Locks exceed maximum capacity** - report infeasibility for distinct valid locked students exceeding the project's places. Reject the new form submission without changing existing locks.
- [x] FIX-05 **Unsupported status** - accept `APPROVED`, `MANDATORY`, and `CONDITIONAL` as active locks, matching the existing form. Reject other values, including non-text values; no status silently disables a lock.

Evidence: `tests/test_fixed_validation.py` (24 examples) and
`test_invalid_lock_form_preserves_existing_lock` (6 web examples).
`validate_fixed_assignments()` is shared by cohort validation and the lock form.
Tests cover conflicts, duplicates, unknown IDs, capacity equality/excess,
statuses, unusable IDs/capacities, contract messages, and unchanged saved locks.
All use synthetic records; no assignment solver is used.

## Feasibility and project demand

Passing input checks does not prove that a feasible assignment exists.
The solver must check combinations of constraints as well.

- [x] FEAS-01 **More students than total places** - report infeasibility under the application's exact-allocation contract. No partial output policy is introduced.
- [x] FEAS-02 **Too few students for required minima** - report infeasibility. Minimum capacities still apply if the lower-level validator's exact-allocation option is disabled.
- [x] FEAS-03 **Mandatory skill unavailable** - require at least one qualified member per mandatory skill on each used project (user confirmed on 2026-10-20). Eligibility respects locks and remaining places.
- [ ] FEAS-04 **Constraints clash in combination** - lock-related coverage shortages are checked. Full combinations remain later solver work: for example, P1 and P2 both require Python with minimum 1, but only S1 is qualified and S2 has no Python. Enough total places and individual coverage checks do not prove feasibility.
- [x] FEAS-05 **Uneven preference demand** - accept as normal competition. Popularity alone is not an input error or infeasibility proof; actual allocations and trade-offs remain later output work.
- [x] FEAS-06 **Zero students allowed** - an unused project needs no mandatory coverage (user confirmed). Warn if an uncovered optional project must remain unused; exclude its capacity from usable places. Minimums, locks, or total demand may force a project to be used.

Evidence: `tests/test_feasibility_validation.py` (12 examples) covers total
capacity, minima, optional projects, lock-related coverage shortages, one
qualified team member, unusable capacity, and uneven demand. These are
necessary input checks, not a complete assignment search. A passing result
means no tested contradiction was found; it does not prove feasibility.

## Run settings

- [x] RUN-01 **Unknown strategy** - accept the dashboard names `PREFERENCE`, `SKILL_FIT`, and `BALANCED`; reject other names and non-text values. Recognising a name does not implement or approve its solver.
- [x] RUN-02 **Invalid alternative count** - accept integers 1 to 4, matching the existing dashboard choices. Reject missing, non-integer, boolean, non-finite, or out-of-range values. The contract default remains 3; a submitted form must provide its count.

Evidence: `tests/test_run_validation.py` (36 examples),
`test_invalid_run_settings_do_not_start_a_mock_run` (5 examples), and
`test_invalid_cohort_is_recorded_without_mock_solutions`. `RunSettingsForm`
parses text before shared domain checks. Rejected settings start no run;
rejected cohorts record diagnostics and zero solutions. Existing valid mock
and infeasible-cohort integration workflows still pass.

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

- [x] DB-01 **Invalid saved records** - check references and raw mandatory flags before a run; check loaded levels, ranks, and capacities with the shared validator. Identify affected records and generate no assignments from rejected inputs. Never convert saved text `"false"` into `True`.
- [x] DB-02 **The database cannot be opened, read, or written** - show a database-unavailable message for locked, unavailable, read-only, or damaged databases. Return HTTP 503; this is not mathematical infeasibility.
- [x] DB-03 **Saving fails partway through** - roll back related records together. Student edits, run saves, scenario replacement, and mock-run input/run writes are atomic. A failed rerun also rolls back its new lock; an unknown scenario leaves input unchanged.
- [ ] DB-04 **Input records change or are deleted after a saved run** - later history work needs a snapshot policy and tests. The current schema can cascade deletion of students or projects to saved assignments. Old runs are not immutable records of their original inputs/results.

Evidence: `tests/test_database_validation.py` (17 examples), five extra bad-capacity
lock checks, and four lock-and-rerun web examples. Tests use real SQLite errors,
invalid saved rows, and failed writes; they check both messages and saved data.
Mock reruns validate the source pair and current inputs before saving a lock.
The mock algorithm and database schema are unchanged.

## Verification and next steps

On 2026-10-20, skill/contract checks returned **89 passed**. The preceding
database/fixed-assignment/integration group returned **113 passed**.

Full suite: **439 passed, 12 xfailed, 4 failed**:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=no -p no:cacheprovider
```

The four failures are the existing CAP-04 real-engine boundary tests;
`execute_run()` is not implemented. No new full-suite failures. The branch
still does not meet the passing-suite requirement for merging. Database
checks ran with access to pytest's separate temporary databases.

Next: audit input entry points and document the Week 1 handoff for deferred output cases. Shared form
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
Fixed-assignment work added 19 domain/contract and 6 web examples. Skill work
was committed and pushed as `b8f3775`; subgroup commits record their test results.
Fixed checks were committed and pushed as `716d52a`. Feasibility work added
12 input examples and records the user's confirmed coverage rule; no solver
or assignment method has been implemented or claimed approved.
Feasibility input checks were pushed as `e8ad14c`. Run settings added 36
domain/form and 6 web examples, with validation now enforced before a mock run.
Run settings were pushed as `6a535ea`. Database work adds the 26 examples
summarised above, clear failure pages, and shared transactions for mock workflows.
Database checks were pushed as `2d8e3fd`. A SKILL-05 follow-up preserves the
omitted catalogue in the convenience API and adds two regression examples.
