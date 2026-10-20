"""Validation logic for students, projects, preferences, and constraints.

This module enforces domain integrity rules and detects edge cases described
in Section 13 of the TECH5 specification, including contradictory constraints,
capacity deficits, unknown identifiers, and skill incompatibilities.
"""

import dataclasses
from typing import Any

from app.domain import models


FIXED_ASSIGNMENT_STATUSES = ("APPROVED", "MANDATORY", "CONDITIONAL")
RUN_STRATEGIES = ("PREFERENCE", "SKILL_FIT", "BALANCED")
MAX_ALTERNATIVES = 4


@dataclasses.dataclass
class ValidationResult:
    """Represents the outcome of cohort data and constraint validation.

    Attributes:
        is_valid: True if input data has no structural or relational errors.
        errors: List of fatal error messages that prevent optimization.
        warnings: List of non-fatal informational notices or edge-case flags.
        is_feasible: False if hard mathematical constraints guarantee no
            feasible assignment exists.
        infeasibility_reasons: Detailed explanations if proven infeasible.
    """

    is_valid: bool = True
    errors: list[str] = dataclasses.field(default_factory=list)
    warnings: list[str] = dataclasses.field(default_factory=list)
    is_feasible: bool = True
    infeasibility_reasons: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializes validation results to a dictionary.

        Returns:
            Dictionary containing validity flags and messages.
        """
        return {
            "is_valid": self.is_valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "is_feasible": self.is_feasible,
            "infeasibility_reasons": list(self.infeasibility_reasons),
        }


def _validate_identifier(
    identifier: object, field: str, errors: list[str]
) -> bool:
    """Checks an ID before it is compared, added to a set, or looked up."""
    if not isinstance(identifier, str):
        errors.append(f"{field} identifier must be text.")
        return False
    if not identifier.strip():
        errors.append(f"{field} identifier cannot be empty or only spaces.")
        return False
    if identifier != identifier.strip():
        errors.append(
            f"{field} identifier {identifier!r} must not start or end with "
            "whitespace. Correct the ID and its references together."
        )
        return False
    return True


def _validate_identifiers(
    students: list[models.Student],
    projects: list[models.Project],
    skills: list[models.Skill],
    fixed_assignments: list[models.FixedAssignment],
) -> list[str]:
    """Checks catalogue IDs, reference IDs, and ownership without changing data."""
    errors: list[str] = []
    student_ids: set[str] = set()
    for index, student in enumerate(students, start=1):
        valid_student_id = _validate_identifier(student.id, f"Student #{index}", errors)
        if valid_student_id:
            if student.id in student_ids:
                errors.append(f"Duplicate student identifier detected: '{student.id}'.")
            student_ids.add(student.id)

        for pref_index, pref in enumerate(student.preferences, start=1):
            field = f"Student '{student.id}' preference #{pref_index}"
            valid_owner = _validate_identifier(pref.student_id, f"{field} student", errors)
            _validate_identifier(pref.project_id, f"{field} project", errors)
            if valid_student_id and valid_owner and pref.student_id != student.id:
                errors.append(
                    f"Preference in student '{student.id}' references student "
                    f"'{pref.student_id}'. It must belong to the containing student. "
                    "Student IDs are case-sensitive."
                )

        for skill_id in student.skills:
            _validate_identifier(skill_id, f"Student '{student.id}' skill", errors)

    project_ids: set[str] = set()
    for index, project in enumerate(projects, start=1):
        valid_project_id = _validate_identifier(project.id, f"Project #{index}", errors)
        if valid_project_id:
            if project.id in project_ids:
                errors.append(f"Duplicate project identifier detected: '{project.id}'.")
            project_ids.add(project.id)

        for req_index, req in enumerate(project.requirements, start=1):
            field = f"Project '{project.id}' requirement #{req_index}"
            valid_owner = _validate_identifier(req.project_id, f"{field} project", errors)
            _validate_identifier(req.skill_id, f"{field} skill", errors)
            if valid_project_id and valid_owner and req.project_id != project.id:
                errors.append(
                    f"Requirement in project '{project.id}' references project "
                    f"'{req.project_id}'. It must belong to the containing project. "
                    "Project IDs are case-sensitive."
                )

    skill_ids: set[str] = set()
    for index, skill in enumerate(skills, start=1):
        if _validate_identifier(skill.id, f"Skill #{index}", errors):
            if skill.id in skill_ids:
                errors.append(f"Duplicate skill identifier detected: '{skill.id}'.")
            skill_ids.add(skill.id)

    for index, fixed in enumerate(fixed_assignments, start=1):
        field = f"Fixed assignment #{index}"
        _validate_identifier(fixed.student_id, f"{field} student", errors)
        _validate_identifier(fixed.project_id, f"{field} project", errors)

    return errors


def _validate_skill_names(skills: list[models.Skill]) -> list[str]:
    """Uses the skill form's name rule: ignore edge spaces and letter case."""
    errors: list[str] = []
    seen_names: dict[str, str] = {}
    for skill in skills:
        if not isinstance(skill.name, str) or not skill.name.strip():
            errors.append(f"Skill '{skill.id}': name must be nonempty text.")
            continue

        compared_name = skill.name.strip().casefold()
        if compared_name in seen_names:
            errors.append(
                f"Duplicate skill name '{skill.name}' for skills "
                f"'{seen_names[compared_name]}' and '{skill.id}'. "
                "Names must differ beyond letter case and surrounding spaces."
            )
        else:
            seen_names[compared_name] = skill.id
    return errors


def _validate_preferences(
    student: models.Student,
    project_ids: set[str],
    result: ValidationResult,
) -> None:
    """Adds preference errors and warnings without changing submitted choices."""
    errors_before = len(result.errors)
    seen_projects: set[str] = set()
    seen_ranks: set[int] = set()
    ranked_projects: set[str] = set()

    for pref in student.preferences:
        if pref.project_id not in project_ids:
            result.errors.append(
                f"Student '{student.id}' ranked unknown project "
                f"'{pref.project_id}'. Project IDs are case-sensitive; "
                "use an exact catalog ID."
            )
        if pref.project_id in seen_projects:
            result.errors.append(
                f"Student '{student.id}' ranked project '{pref.project_id}' "
                "more than once. List each project only once."
            )
        seen_projects.add(pref.project_id)

        if type(pref.rank) is not int or pref.rank < 1:
            result.errors.append(
                f"Student '{student.id}', project '{pref.project_id}': "
                "preference rank must be a positive whole number."
            )
            continue

        if pref.rank in seen_ranks:
            result.errors.append(
                f"Student '{student.id}' uses rank {pref.rank} more than once. "
                "Give each project a different rank; tied ranks are not supported."
            )
        seen_ranks.add(pref.rank)
        if pref.project_id in project_ids:
            ranked_projects.add(pref.project_id)

    if not student.preferences:
        result.warnings.append(
            f"Student '{student.display_name}' ({student.id}) has submitted "
            "no ranked preferences; at least 3 are expected. "
            "The student may receive an unranked project."
        )
    elif len(ranked_projects) < 3:
        result.warnings.append(
            f"Student '{student.id}' ranked {len(ranked_projects)} distinct "
            "available projects; at least 3 are expected. "
            "The student may receive an unranked project."
        )

    # Check gaps only after the individual entries have passed validation.
    if student.preferences and len(result.errors) == errors_before:
        expected_ranks = set(range(1, len(student.preferences) + 1))
        if seen_ranks != expected_ranks:
            result.errors.append(
                f"Student '{student.id}': preference ranks must start at 1 "
                f"and continue without gaps through {len(student.preferences)}. "
                "Correct the submitted ranks; they have not been renumbered."
            )


def _validate_skill_level(level: object, field: str, errors: list[str]) -> None:
    """Checks stored proficiency before comparisons; booleans are not levels."""
    if type(level) is not int or not 1 <= level <= 5:
        errors.append(f"{field}: level must be a whole number from 1 to 5.")


def _validate_skill_data(
    students: list[models.Student],
    projects: list[models.Project],
    skills: list[models.Skill] | None,
    result: ValidationResult,
) -> None:
    """Collects skill errors before mandatory matching uses the data."""
    defined_skill_ids = None if skills is None else {skill.id for skill in skills}
    has_skill_references = (
        any(student.skills for student in students)
        or any(project.requirements for project in projects)
    )
    if skills is None and has_skill_references:
        result.warnings.append(
            "The skill catalogue was omitted; skill references could not be "
            "checked against it. Supply a catalogue to verify the skill IDs."
        )

    for student in students:
        for skill_id, level in student.skills.items():
            field = f"Student '{student.id}', skill '{skill_id}'"
            _validate_skill_level(level, field, result.errors)
            if defined_skill_ids is not None and skill_id not in defined_skill_ids:
                result.errors.append(
                    f"Student '{student.id}' lists unknown skill '{skill_id}'. "
                    "Skill IDs are case-sensitive; use an exact catalog ID."
                )

    for project in projects:
        seen_skills: set[str] = set()
        for requirement in project.requirements:
            skill_id = requirement.skill_id
            field = f"Project '{project.id}', skill '{skill_id}'"
            _validate_skill_level(requirement.minimum_level, field, result.errors)
            if type(requirement.is_mandatory) is not bool:
                result.errors.append(f"{field}: mandatory flag must be True or False.")
            if skill_id in seen_skills:
                result.errors.append(
                    f"Project '{project.id}' lists requirement skill '{skill_id}' "
                    "more than once. Correct the duplicate requirements."
                )
            seen_skills.add(skill_id)
            if defined_skill_ids is not None and skill_id not in defined_skill_ids:
                result.errors.append(
                    f"Project '{project.id}' demands unknown skill '{skill_id}'. "
                    "Skill IDs are case-sensitive; use an exact catalog ID."
                )

def validate_fixed_assignments(
    fixed_assignments: list[models.FixedAssignment],
    student_ids: set[str],
    project_capacities: dict[str, int],
) -> ValidationResult:
    """Checks locks against known IDs and validated maximum capacities.

    All supported statuses denote active locks, matching the existing form.
    Duplicate or conflicting rows are rejected before capacity is counted.
    """
    result = ValidationResult()
    student_projects: dict[str, str] = {}
    project_counts: dict[str, int] = {}
    for index, fixed in enumerate(fixed_assignments, start=1):
        field = f"Fixed assignment #{index}"
        valid_student = _validate_identifier(fixed.student_id, f"{field} student", result.errors)
        valid_project = _validate_identifier(fixed.project_id, f"{field} project", result.errors)
        if not valid_student or not valid_project:
            continue
        if not isinstance(fixed.status, str) or fixed.status not in FIXED_ASSIGNMENT_STATUSES:
            result.errors.append(
                f"Fixed assignment for student '{fixed.student_id}' has unsupported status "
                f"{fixed.status!r}. Use APPROVED, MANDATORY, or CONDITIONAL; all are active locks."
            )
        if fixed.student_id not in student_ids:
            result.errors.append(
                f"Fixed assignment references unknown student '{fixed.student_id}'. "
                "Student IDs are case-sensitive; use an exact cohort ID."
            )
        if fixed.project_id not in project_capacities:
            result.errors.append(
                f"Fixed assignment references unknown project '{fixed.project_id}'. "
                "Project IDs are case-sensitive; use an exact catalog ID."
            )
        if fixed.student_id in student_projects:
            previous_project = student_projects[fixed.student_id]
            if previous_project == fixed.project_id:
                result.errors.append(
                    f"Duplicate fixed assignment: student '{fixed.student_id}' is locked "
                    f"to project '{fixed.project_id}' more than once."
                )
            else:
                result.errors.append(
                    f"Contradictory fixed assignment: student '{fixed.student_id}' is "
                    f"locked to both '{previous_project}' and '{fixed.project_id}'. "
                    "Release the existing lock before choosing another project."
                )
        else:
            student_projects[fixed.student_id] = fixed.project_id
            project_counts[fixed.project_id] = project_counts.get(fixed.project_id, 0) + 1

    if result.errors:
        result.is_valid = False
        return result

    for project_id, count in project_counts.items():
        if count > project_capacities[project_id]:
            message = (
                f"Fixed assignments ({count}) for project '{project_id}' exceed its "
                f"maximum capacity ({project_capacities[project_id]})."
            )
            result.errors.append(message)
            result.infeasibility_reasons.append(message)
            result.is_feasible = False
    result.is_valid = not result.errors
    return result


def _check_mandatory_feasibility(
    students: list[models.Student],
    projects: list[models.Project],
    fixed_assignments: list[models.FixedAssignment],
    enforce_exact_allocation: bool,
    result: ValidationResult,
) -> None:
    """Checks necessary team coverage, allowing an optional project to stay unused.

    Each used project needs one eligible member per mandatory skill. These
    individual checks do not prove that all projects can be staffed together.
    """
    locked_projects = {fixed.student_id: fixed.project_id for fixed in fixed_assignments}
    total_max_capacity = sum(project.max_capacity for project in projects)
    usable_max_capacity = 0
    for project in projects:
        locked_count = sum(project_id == project.id for project_id in locked_projects.values())
        has_open_place = locked_count < project.max_capacity
        project_must_be_used = project.min_capacity > 0 or locked_count > 0
        if enforce_exact_allocation and len(students) > total_max_capacity - project.max_capacity:
            project_must_be_used = True

        project_is_usable = True
        for requirement in project.requirements:
            if not requirement.is_mandatory:
                continue
            qualified_students = []
            for student in students:
                locked_project = locked_projects.get(student.id)
                if locked_project is not None and locked_project != project.id:
                    continue
                if locked_project != project.id and not has_open_place:
                    continue
                if student.get_skill_level(requirement.skill_id) >= requirement.minimum_level:
                    qualified_students.append(student.id)
            if qualified_students:
                continue

            project_is_usable = False
            detail = (
                f"No eligible student meets mandatory skill '{requirement.skill_id}' "
                f"(level {requirement.minimum_level}) for project '{project.id}', "
                "after respecting fixed locks and available places."
            )
            if project_must_be_used:
                message = f"Mandatory requirement impossible: {detail}"
                result.errors.append(message)
                result.infeasibility_reasons.append(message)
                result.is_feasible = False
            else:
                result.warnings.append(f"{detail} This optional project must remain unused.")

        if project_is_usable:
            usable_max_capacity += project.max_capacity

    if enforce_exact_allocation and usable_max_capacity < total_max_capacity and len(students) > usable_max_capacity:
        message = (
            f"Mandatory skills and fixed locks leave usable project places "
            f"({usable_max_capacity}) below the cohort size ({len(students)})."
        )
        result.errors.append(message)
        result.infeasibility_reasons.append(message)
        result.is_feasible = False


def validate_run_settings(strategy_key: object, max_alternatives: object) -> ValidationResult:
    """Checks the names and 1-to-4 count supported by the current dashboard.

    Recognising a strategy name does not implement or approve its solver.
    """
    result = ValidationResult()
    if not isinstance(strategy_key, str) or strategy_key not in RUN_STRATEGIES:
        result.errors.append(
            "Unknown assignment strategy. Use PREFERENCE, SKILL_FIT, or BALANCED."
        )
    if type(max_alternatives) is not int or not 1 <= max_alternatives <= MAX_ALTERNATIVES:
        result.errors.append("Requested alternatives must be a whole number from 1 to 4.")
    result.is_valid = not result.errors
    return result


def validate_cohort(
    students: list[models.Student],
    projects: list[models.Project],
    skills: list[models.Skill] | None = None,
    fixed_assignments: list[models.FixedAssignment] | None = None,
    enforce_exact_allocation: bool = True,
) -> ValidationResult:
    """Validates complete cohort inputs and checks for structural infeasibility.

    Args:
        students: List of students in the cohort.
        projects: List of available semester projects.
        skills: Optional list of defined skills in the catalog.
        fixed_assignments: Optional list of locked pre-allocations.
        enforce_exact_allocation: Whether every student must receive a project.

    Returns:
        A ValidationResult detailing validity, warnings, and feasibility.
        Empty cohorts or project catalogs are rejected before other checks.
        Identifier and skill-name errors are rejected before feasibility checks.
        IDs are case-sensitive text with no surrounding whitespace.
        Non-integer capacities are rejected before capacity calculations.
        Short preference lists warn; duplicate projects, tied or invalid ranks,
        rank gaps, and unknown projects are rejected.
        Skill levels must be integers from 1 to 5 and mandatory flags booleans.
        Supplied skill catalogues enforce references, including empty catalogues.
        An omitted catalogue warns when references cannot be checked against it.
    """
    result = ValidationResult()

    if not students:
        result.errors.append("Student cohort cannot be empty.")
    if not projects:
        result.errors.append("Project catalog cannot be empty.")

    if not students or not projects:
        result.is_valid = False
        return result

    result.errors.extend(
        _validate_identifiers(students, projects, skills or [], fixed_assignments or [])
    )
    result.errors.extend(_validate_skill_names(skills or []))
    if result.errors:
        result.is_valid = False
        return result

    student_ids = {student.id for student in students}
    project_ids = {project.id for project in projects}

    has_invalid_capacity = False
    for project in projects:
        if type(project.min_capacity) is not int:
            result.errors.append(
                f"Project '{project.id}': minimum capacity must be a whole "
                "number."
            )
            has_invalid_capacity = True
        if type(project.max_capacity) is not int:
            result.errors.append(
                f"Project '{project.id}': maximum capacity must be a whole "
                "number."
            )
            has_invalid_capacity = True

    if has_invalid_capacity:
        result.is_valid = False
        return result

    _validate_skill_data(students, projects, skills, result)

    total_min_capacity = 0
    total_max_capacity = 0
    for project in projects:
        if project.max_capacity <= 0:
            result.errors.append(
                f"Project '{project.id}' has non-positive max capacity: "
                f"{project.max_capacity}."
            )
        if project.min_capacity < 0:
            result.errors.append(
                f"Project '{project.id}' has negative min capacity: "
                f"{project.min_capacity}."
            )
        if project.min_capacity > project.max_capacity:
            result.errors.append(
                f"Project '{project.id}' has min capacity "
                f"({project.min_capacity}) exceeding max capacity "
                f"({project.max_capacity})."
            )

        total_min_capacity += project.min_capacity
        total_max_capacity += project.max_capacity

    if len(projects) < 3:
        result.warnings.append(
            f"Fewer than 3 projects are offered ({len(projects)} available); "
            "students cannot rank "
            "the expected minimum of 3."
        )

    for student in students:
        _validate_preferences(student, project_ids, result)

    if fixed_assignments:
        fixed_result = validate_fixed_assignments(
            fixed_assignments, student_ids,
            {project.id: project.max_capacity for project in projects},
        )
        result.errors.extend(fixed_result.errors)
        result.infeasibility_reasons.extend(fixed_result.infeasibility_reasons)
        if not fixed_result.is_feasible:
            result.is_feasible = False

    if enforce_exact_allocation and len(students) > total_max_capacity:
        result.is_feasible = False
        msg = (
            f"Insufficient overall capacity: total cohort size "
            f"({len(students)}) exceeds aggregate maximum project capacity "
            f"({total_max_capacity})."
        )
        result.errors.append(msg)
        result.infeasibility_reasons.append(msg)

    if len(students) < total_min_capacity:
        result.is_feasible = False
        msg = (
            f"Cohort size ({len(students)}) is below aggregate minimum "
            f"project capacity ({total_min_capacity})."
        )
        result.errors.append(msg)
        result.infeasibility_reasons.append(msg)

    if result.errors:
        result.is_valid = False
        return result

    _check_mandatory_feasibility(
        students, projects, fixed_assignments or [], enforce_exact_allocation, result
    )

    if result.errors:
        result.is_valid = False

    return result
