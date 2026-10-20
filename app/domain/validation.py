"""Validation logic for students, projects, preferences, and constraints.

This module enforces domain integrity rules and detects edge cases described
in Section 13 of the TECH5 specification, including contradictory constraints,
capacity deficits, unknown identifiers, and skill incompatibilities.
"""

import dataclasses
from typing import Any

from app.domain import models


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

    defined_skill_ids = {s.id for s in skills} if skills else None

    for student in students:
        if not student.preferences:
            result.warnings.append(
                f"Student '{student.display_name}' ({student.id}) has "
                "submitted no ranked preferences."
            )

        seen_ranks: set[int] = set()
        seen_preferred_projects: set[str] = set()
        for pref in student.preferences:
            if pref.project_id not in project_ids:
                result.errors.append(
                    f"Student '{student.id}' ranked unknown project "
                    f"'{pref.project_id}'. Project IDs are case-sensitive; "
                    "use an exact catalog ID."
                )
            if pref.project_id in seen_preferred_projects:
                result.warnings.append(
                    f"Student '{student.id}' has multiple preferences for "
                    f"project '{pref.project_id}'."
                )
            seen_preferred_projects.add(pref.project_id)

            if pref.rank in seen_ranks:
                result.warnings.append(
                    f"Student '{student.id}' has duplicate rank {pref.rank}."
                )
            seen_ranks.add(pref.rank)

        if defined_skill_ids:
            for s_id in student.skills:
                if s_id not in defined_skill_ids:
                    result.warnings.append(
                        f"Student '{student.id}' lists uncatalogued skill "
                        f"'{s_id}'. Skill IDs are case-sensitive; "
                        "check the catalog ID."
                    )

    for project in projects:
        if defined_skill_ids:
            for req in project.requirements:
                if req.skill_id not in defined_skill_ids:
                    result.warnings.append(
                        f"Project '{project.id}' demands uncatalogued skill "
                        f"'{req.skill_id}'. Skill IDs are case-sensitive; "
                        "check the catalog ID."
                    )

    if fixed_assignments:
        fixed_student_counts: dict[str, int] = {}
        fixed_project_counts: dict[str, int] = {}

        for fixed in fixed_assignments:
            if fixed.student_id not in student_ids:
                result.errors.append(
                    f"Fixed assignment references unknown student "
                    f"'{fixed.student_id}'. Student IDs are case-sensitive; "
                    "use an exact cohort ID."
                )
            if fixed.project_id not in project_ids:
                result.errors.append(
                    f"Fixed assignment references unknown project "
                    f"'{fixed.project_id}'. Project IDs are case-sensitive; "
                    "use an exact catalog ID."
                )

            fixed_student_counts[fixed.student_id] = (
                fixed_student_counts.get(fixed.student_id, 0) + 1
            )
            fixed_project_counts[fixed.project_id] = (
                fixed_project_counts.get(fixed.project_id, 0) + 1
            )

        for s_id, count in fixed_student_counts.items():
            if count > 1:
                result.errors.append(
                    f"Contradictory fixed assignment: student '{s_id}' is "
                    f"fixed to {count} different projects."
                )

        for p in projects:
            p_fixed = fixed_project_counts.get(p.id, 0)
            if p_fixed > p.max_capacity:
                result.is_feasible = False
                msg = (
                    f"Fixed assignments ({p_fixed}) for project '{p.id}' "
                    f"exceed its maximum capacity ({p.max_capacity})."
                )
                result.errors.append(msg)
                result.infeasibility_reasons.append(msg)

    if enforce_exact_allocation and len(students) > total_max_capacity:
        result.is_feasible = False
        msg = (
            f"Insufficient overall capacity: total cohort size "
            f"({len(students)}) exceeds aggregate maximum project capacity "
            f"({total_max_capacity})."
        )
        result.errors.append(msg)
        result.infeasibility_reasons.append(msg)

    if enforce_exact_allocation and len(students) < total_min_capacity:
        result.is_feasible = False
        msg = (
            f"Cohort size ({len(students)}) is below aggregate minimum "
            f"project capacity ({total_min_capacity})."
        )
        result.errors.append(msg)
        result.infeasibility_reasons.append(msg)

    for project in projects:
        for req in project.requirements:
            if req.is_mandatory:
                qualified_students = [
                    s
                    for s in students
                    if s.get_skill_level(req.skill_id) >= req.minimum_level
                ]
                if not qualified_students:
                    result.is_feasible = False
                    msg = (
                        f"Mandatory requirement impossible: No student in "
                        f"cohort meets mandatory skill '{req.skill_id}' "
                        f"(level {req.minimum_level}) for project "
                        f"'{project.id}'."
                    )
                    result.errors.append(msg)
                    result.infeasibility_reasons.append(msg)

    if result.errors:
        result.is_valid = False

    return result
