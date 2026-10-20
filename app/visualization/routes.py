"""Web routes and controller logic for Component A (Visualization).

This module provides interactive CRUD interfaces, scenario seeders, optimization
triggering, multi-solution visual comparisons, and recommendations.
"""

import collections
import csv
import dataclasses
import io
import re
import sqlite3
from typing import Any

import flask

from app.contract import contract
from app.contract import mocks
from app.domain import models
from app.engine import recommendations
from app.engine import solvers
from app.persistence import repositories
from app.samples import demo_data
from app.visualization import auth
from app.visualization import forms

web_bp = flask.Blueprint("visualization_web", __name__)

_SKILL_ID_PATTERN = re.compile(r"[a-z0-9_]+")
_COMPARE_RUN_LIMIT = 20


@web_bp.app_context_processor
def inject_template_globals() -> dict[str, Any]:
    """Injects authorization helpers and active role into templates."""
    return {
        "current_role": auth.get_current_role(),
        "all_roles": auth.UserRole.ALL_ROLES,
        "can_edit": auth.can_edit_cohort_data(),
        "can_optimize": auth.can_trigger_optimization(),
    }


@web_bp.post("/set-role")
def set_role() -> flask.Response:
    """Updates the active user role prototype."""
    role = flask.request.form.get("role", auth.UserRole.ADMIN)
    auth.set_current_role(role)
    role_name = auth.UserRole.ALL_ROLES.get(role, role)
    flask.flash(f"Switched role to {role_name}.", "info")
    target = flask.request.referrer or flask.url_for(
        "visualization_web.dashboard"
    )
    return flask.redirect(target)


@web_bp.get("/")
def dashboard() -> str:
    """Renders main dashboard overview with cohort metrics and runs."""
    stud_repo = repositories.StudentRepository()
    proj_repo = repositories.ProjectRepository()
    fixed_repo = repositories.FixedAssignmentRepository()
    run_repo = repositories.RunRepository()

    students = stud_repo.list_all()
    projects = proj_repo.list_all()
    fixed_assignments = fixed_repo.list_all()
    runs = run_repo.list_runs(limit=10)

    total_capacity = sum(p.max_capacity for p in projects)
    latest_run = runs[0] if runs else None

    return flask.render_template(
        "dashboard.html",
        student_count=len(students),
        project_count=len(projects),
        total_capacity=total_capacity,
        fixed_count=len(fixed_assignments),
        recent_runs=runs,
        latest_run=latest_run,
    )


# -----------------------------------------------------------------------------
# Students CRUD
# -----------------------------------------------------------------------------


@web_bp.get("/students")
def list_students() -> str:
    """Lists all students with their proficiencies and ranked preferences."""
    students = repositories.StudentRepository().list_all()
    projects = repositories.ProjectRepository().list_all()
    skills = repositories.SkillRepository().list_all()
    return flask.render_template(
        "students.html",
        students=students,
        projects=projects,
        skills=skills,
    )


@web_bp.get("/students/new")
def new_student_form() -> str:
    """Displays form to create a new student."""
    projects = repositories.ProjectRepository().list_all()
    skills = repositories.SkillRepository().list_all()
    return flask.render_template(
        "student_form.html",
        student=None,
        projects=projects,
        skills=skills,
    )


def _check_valid_student_data(
    student_id: str,
    student_name: str,
    available_students: dict[str, str],
) -> bool:
    """Checks if the student data is valid
    Args:
        student_id: Target student identifier.
        student_name: Target student name.
        available_students: Map of existing students id and name.
    Returns:
        A list of invalid students.
    """
    

    valid = 1

    if student_id in available_students:
        valid = 0
    elif student_name in available_students.values():
        valid = 0


    return valid


def _parse_and_validate_preferences(
    student_id: str,
    pref_raw: str,
    available_projects: dict[str, models.Project],
) -> tuple[list[models.Preference], list[str]]:
    """Parses and validates comma-separated project preferences.

    Args:
        student_id: Target student identifier.
        pref_raw: Comma-separated project IDs string from user input.
        available_projects: Map of valid project ID to Project model.

    Returns:
        A tuple of (valid_preferences_list, invalid_project_ids_list).
        Prefer exact IDs. Accept a case-insensitive match only when unique.
        Unknown, ambiguous, or repeated choices must be corrected before saving.
    """
    raw_tokens = [p.strip() for p in pref_raw.split(",") if p.strip()]

    valid_prefs: list[models.Preference] = []
    invalid_ids: list[str] = []
    seen: set[str] = set()

    for token in raw_tokens:
        resolved_id = None
        if token in available_projects:
            resolved_id = token
        else:
            matching_ids = [
                project_id for project_id in available_projects
                if project_id.casefold() == token.casefold()
            ]
            if len(matching_ids) == 1:
                resolved_id = matching_ids[0]

        if resolved_id is None:
            invalid_ids.append(token)
            continue

        if resolved_id in seen:
            invalid_ids.append(f"{token} (project '{resolved_id}' is repeated)")
            continue

        seen.add(resolved_id)
        valid_prefs.append(
            models.Preference(
                student_id=student_id,
                project_id=resolved_id,
                rank=len(valid_prefs) + 1,
            )
        )

    return valid_prefs, invalid_ids


@web_bp.post("/students/new")
def create_student() -> flask.Response:
    """Processes creation of a new student."""
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_students"))

    s_id = flask.request.form.get("id", "").strip()
    name = flask.request.form.get("display_name", "").strip() or s_id

    available_students = {
        s.id: s.display_name for s in repositories.StudentRepository().list_all()
    }

    if not _check_valid_student_data(s_id,name, available_students):
        flask.flash(f"Student ID: {s_id}, or Name: {name} already exists.", "danger")
        return flask.redirect(
            flask.url_for("visualization_web.new_student_form")
        )

    if not s_id:
        flask.flash("Student ID cannot be empty.", "warning")
        return flask.redirect(
            flask.url_for("visualization_web.new_student_form")
        )

    skill_form = forms.StudentSkillsForm(
        flask.request.form, [skill.id for skill in repositories.SkillRepository().list_all()]
    )
    skills_dict = skill_form.to_skills()
    if skills_dict is None:
        for error in skill_form.errors:
            flask.flash(error, "danger")
        return flask.redirect(flask.url_for("visualization_web.new_student_form"))

    # Parse and validate preferences against catalog
    available_projects = {
        p.id: p for p in repositories.ProjectRepository().list_all()
    }
    pref_raw = flask.request.form.get("preferences_text", "")
    preferences, invalid_proj_ids = _parse_and_validate_preferences(
        s_id, pref_raw, available_projects
    )

    if invalid_proj_ids:
        valid_list = (
            ", ".join(sorted(available_projects.keys())) or "None available"
        )
        flask.flash(
            f"Invalid project ID(s) in preferences: "
            f"{', '.join(invalid_proj_ids)}. "
            f"Available projects: {valid_list}. "
            "Use the exact spelling when IDs differ only by letter case.",
            "danger",
        )
        return flask.redirect(
            flask.url_for("visualization_web.new_student_form")
        )

    student = models.Student(
        id=s_id,
        display_name=name,
        skills=skills_dict,
        preferences=preferences,
    )
    try:
        repositories.StudentRepository().save(student)
    except sqlite3.IntegrityError as exc:
        flask.flash(
            f"Database constraint error while saving student: {exc}",
            "danger",
        )
        return flask.redirect(
            flask.url_for("visualization_web.new_student_form")
        )

    flask.flash(f"Student '{name}' ({s_id}) created successfully.", "success")
    return flask.redirect(flask.url_for("visualization_web.list_students"))


@web_bp.get("/students/<student_id>/edit")
def edit_student_form(student_id: str) -> Any:
    """Displays form to edit an existing student."""
    student = repositories.StudentRepository().get_by_id(student_id)
    if not student:
        flask.flash(f"Student '{student_id}' not found.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_students"))

    projects = repositories.ProjectRepository().list_all()
    skills = repositories.SkillRepository().list_all()
    return flask.render_template(
        "student_form.html",
        student=student,
        projects=projects,
        skills=skills,
    )


@web_bp.post("/students/<student_id>/edit")
def update_student(student_id: str) -> flask.Response:
    """Updates an existing student entity."""
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_students"))

    name = (
        flask.request.form.get("display_name", "").strip() or student_id
    )

    skill_form = forms.StudentSkillsForm(
        flask.request.form, [skill.id for skill in repositories.SkillRepository().list_all()]
    )
    skills_dict = skill_form.to_skills()
    if skills_dict is None:
        for error in skill_form.errors:
            flask.flash(error, "danger")
        return flask.redirect(
            flask.url_for("visualization_web.edit_student_form", student_id=student_id)
        )

    # Parse and validate preferences against catalog
    available_projects = {
        p.id: p for p in repositories.ProjectRepository().list_all()
    }
    pref_raw = flask.request.form.get("preferences_text", "")
    preferences, invalid_proj_ids = _parse_and_validate_preferences(
        student_id, pref_raw, available_projects
    )

    if invalid_proj_ids:
        valid_list = (
            ", ".join(sorted(available_projects.keys())) or "None available"
        )
        flask.flash(
            f"Invalid project ID(s) in preferences: "
            f"{', '.join(invalid_proj_ids)}. "
            f"Available projects: {valid_list}. "
            "Use the exact spelling when IDs differ only by letter case.",
            "danger",
        )
        return flask.redirect(
            flask.url_for(
                "visualization_web.edit_student_form", student_id=student_id
            )
        )

    student = models.Student(
        id=student_id,
        display_name=name,
        skills=skills_dict,
        preferences=preferences,
    )
    try:
        repositories.StudentRepository().save(student)
    except sqlite3.IntegrityError as exc:
        flask.flash(
            f"Database constraint error while updating student: {exc}",
            "danger",
        )
        return flask.redirect(
            flask.url_for(
                "visualization_web.edit_student_form", student_id=student_id
            )
        )

    flask.flash(f"Student '{student_id}' updated.", "success")
    return flask.redirect(flask.url_for("visualization_web.list_students"))


@web_bp.post("/students/<student_id>/delete")
def delete_student(student_id: str) -> flask.Response:
    """Deletes a student."""
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_students"))

    repositories.StudentRepository().delete(student_id)
    flask.flash(f"Student '{student_id}' removed.", "info")
    return flask.redirect(flask.url_for("visualization_web.list_students"))


# -----------------------------------------------------------------------------
# Projects CRUD
# -----------------------------------------------------------------------------


@web_bp.get("/projects")
def list_projects() -> str:
    """Displays project catalog and capacity definitions."""
    projects = repositories.ProjectRepository().list_all()
    skills = repositories.SkillRepository().list_all()
    return flask.render_template(
        "projects.html",
        projects=projects,
        skills=skills,
        skill_names={sk.id: sk.name for sk in skills},
        usage=_project_usage(),
    )


def _project_usage() -> dict[str, dict[str, int]]:
    """Counts the records that reference each project.

    Deleting a project cascades to these records, so the catalog shows the
    counts in the delete confirmation.

    Returns:
        Mapping of project ID to counts of student preferences ranking the
        project and fixed assignments to it.
    """
    usage: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"preferences": 0, "fixed": 0}
    )
    for student in repositories.StudentRepository().list_all():
        for pref in student.preferences:
            usage[pref.project_id]["preferences"] += 1
    for fixed in repositories.FixedAssignmentRepository().list_all():
        usage[fixed.project_id]["fixed"] += 1
    return dict(usage)


@web_bp.get("/projects/new")
def new_project_form() -> str:
    """Displays form to create a semester project."""
    skills = repositories.SkillRepository().list_all()
    return flask.render_template(
        "project_form.html", project=None, skills=skills, req_by_skill={}
    )


@web_bp.post("/projects/new")
def create_project() -> flask.Response:
    """Processes creation of a project and its skill requirements."""
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_projects"))

    skills = repositories.SkillRepository().list_all()
    form = forms.ProjectForm(flask.request.form, [sk.id for sk in skills])
    project = form.to_project()
    if project is None:
        for error in form.errors:
            flask.flash(error, "warning")
        return flask.redirect(
            flask.url_for("visualization_web.new_project_form")
        )

    repo = repositories.ProjectRepository()
    # save() is an upsert, so an existing ID would be silently overwritten.
    if repo.get_by_id(project.id) is not None:
        flask.flash(f"Project '{project.id}' already exists.", "danger")
        return flask.redirect(
            flask.url_for("visualization_web.new_project_form")
        )

    try:
        repo.save(project)
    except sqlite3.Error as exc:
        flask.flash(f"Database error while saving project: {exc}", "danger")
        return flask.redirect(
            flask.url_for("visualization_web.new_project_form")
        )

    flask.flash(
        f"Project '{project.title}' ({project.id}) created successfully.",
        "success",
    )
    return flask.redirect(flask.url_for("visualization_web.list_projects"))


@web_bp.get("/projects/<project_id>/edit")
def edit_project_form(project_id: str) -> Any:
    """Displays form to edit a project."""
    project = repositories.ProjectRepository().get_by_id(project_id)
    if not project:
        flask.flash(f"Project '{project_id}' not found.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_projects"))

    skills = repositories.SkillRepository().list_all()
    return flask.render_template(
        "project_form.html",
        project=project,
        skills=skills,
        req_by_skill={req.skill_id: req for req in project.requirements},
    )


@web_bp.post("/projects/<project_id>/edit")
def update_project(project_id: str) -> flask.Response:
    """Updates an existing project and replaces its skill requirements."""
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_projects"))

    repo = repositories.ProjectRepository()
    if repo.get_by_id(project_id) is None:
        flask.flash(f"Project '{project_id}' not found.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_projects"))

    skills = repositories.SkillRepository().list_all()
    form = forms.ProjectForm(
        flask.request.form, [sk.id for sk in skills], project_id=project_id
    )
    project = form.to_project()
    if project is None:
        for error in form.errors:
            flask.flash(error, "warning")
        return flask.redirect(
            flask.url_for(
                "visualization_web.edit_project_form", project_id=project_id
            )
        )

    try:
        repo.save(project)
    except sqlite3.Error as exc:
        flask.flash(f"Database error while updating project: {exc}", "danger")
        return flask.redirect(
            flask.url_for(
                "visualization_web.edit_project_form", project_id=project_id
            )
        )

    flask.flash(f"Project '{project_id}' updated.", "success")
    return flask.redirect(flask.url_for("visualization_web.list_projects"))


@web_bp.post("/projects/<project_id>/delete")
def delete_project(project_id: str) -> flask.Response:
    """Deletes a project.

    The database cascades the delete to the project's requirements, student
    preferences for it, fixed assignments to it and its assignments in saved
    runs. The catalog warns about this before the form is submitted.
    """
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_projects"))

    if repositories.ProjectRepository().delete(project_id):
        flask.flash(f"Project '{project_id}' removed.", "info")
    else:
        flask.flash(f"Project '{project_id}' not found.", "warning")
    return flask.redirect(flask.url_for("visualization_web.list_projects"))


# -----------------------------------------------------------------------------
# Skills CRUD & Preferences Editor
# -----------------------------------------------------------------------------


def _validate_skill_input(
    skill_id: str,
    name: str,
    existing_skills: list[models.Skill],
) -> tuple[str, list[str]]:
    """Normalizes and validates the input of a new skill.

    The identifier is stripped and lowercased before it is checked, so that
    "  PY " is stored as "py". Duplicate names ignore case and edge spaces
    in both the new name and existing names.

    Args:
        skill_id: Raw skill identifier from user input.
        name: Raw skill name from user input.
        existing_skills: Skills already present in the catalog.

    Returns:
        A tuple of (normalized_skill_id, error_messages). The list of error
        messages is empty when the input is valid.
    """
    norm_id = skill_id.strip().lower()
    norm_name = name.strip()
    errors: list[str] = []

    if not norm_id:
        errors.append("Skill ID cannot be empty.")
    elif not _SKILL_ID_PATTERN.fullmatch(norm_id):
        errors.append(
            f"Invalid skill ID '{norm_id}': use only lowercase letters, "
            "digits and underscores."
        )
    elif any(s.id == norm_id for s in existing_skills):
        errors.append(f"Skill ID '{norm_id}' already exists.")

    if not norm_name:
        errors.append("Skill name cannot be empty.")
    elif norm_name.casefold() in {s.name.strip().casefold() for s in existing_skills}:
        errors.append(f"Skill name '{norm_name}' already exists.")

    return norm_id, errors


def _compute_skill_usage(
    skills: list[models.Skill],
    projects: list[models.Project],
    students: list[models.Student],
) -> dict[str, dict[str, Any]]:
    """Computes where each skill is used across projects and students.

    Args:
        skills: Skills of the catalog.
        projects: All projects with their requirements.
        students: All students with their proficiencies.

    Returns:
        A map of skill ID to a dict with the keys "projects" (IDs of the
        projects requiring the skill), "mandatory" (IDs of the projects
        requiring it as mandatory) and "students" (number of students with
        a proficiency level above zero).
    """
    usage: dict[str, dict[str, Any]] = {
        s.id: {"projects": [], "mandatory": [], "students": 0}
        for s in skills
    }
    for project in projects:
        for req in project.requirements:
            entry = usage.get(req.skill_id)
            if entry is None:
                continue
            entry["projects"].append(project.id)
            if req.is_mandatory:
                entry["mandatory"].append(project.id)
    for student in students:
        for skill_id, level in student.skills.items():
            if level > 0 and skill_id in usage:
                usage[skill_id]["students"] += 1
    return usage


@web_bp.get("/skills")
def list_skills() -> str:
    """Lists skill catalog records with their usage across the cohort."""
    skills = repositories.SkillRepository().list_all()
    projects = repositories.ProjectRepository().list_all()
    students = repositories.StudentRepository().list_all()
    return flask.render_template(
        "skills.html",
        skills=skills,
        usage=_compute_skill_usage(skills, projects, students),
    )


@web_bp.post("/skills/new")
def create_skill() -> flask.Response:
    """Creates a new skill record."""
    target = flask.url_for("visualization_web.list_skills")
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(target)

    raw_id = flask.request.form.get("id", "")
    name = flask.request.form.get("name", "").strip()
    description = flask.request.form.get("description", "").strip()

    repo = repositories.SkillRepository()
    skill_id, errors = _validate_skill_input(raw_id, name, repo.list_all())
    if errors:
        for message in errors:
            flask.flash(message, "danger")
        return flask.redirect(target)

    try:
        repo.save(
            models.Skill(id=skill_id, name=name, description=description)
        )
    except sqlite3.IntegrityError as exc:
        flask.flash(
            f"Database constraint error while saving skill: {exc}",
            "danger",
        )
        return flask.redirect(target)

    flask.flash(f"Skill '{name}' ({skill_id}) created successfully.", "success")
    return flask.redirect(target)


@web_bp.post("/skills/<skill_id>/delete")
def delete_skill(skill_id: str) -> flask.Response:
    """Deletes a skill record and reports the requirements removed with it."""
    target = flask.url_for("visualization_web.list_skills")
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(target)

    repo = repositories.SkillRepository()
    if repo.get_by_id(skill_id) is None:
        flask.flash(f"Skill '{skill_id}' not found.", "warning")
        return flask.redirect(target)

    # Measure the impact first: the schema cascades the deletion into
    # project requirements and student proficiencies.
    usage = _compute_skill_usage(
        repo.list_all(),
        repositories.ProjectRepository().list_all(),
        repositories.StudentRepository().list_all(),
    )[skill_id]
    repo.delete(skill_id)

    parts = [f"Skill '{skill_id}' deleted."]
    if usage["projects"]:
        parts.append(
            f"Removed from project(s): {', '.join(usage['projects'])}."
        )
    if usage["students"]:
        parts.append(f"{usage['students']} student(s) lost this proficiency.")
    flask.flash(" ".join(parts), "info")

    if usage["mandatory"]:
        flask.flash(
            f"Warning: skill '{skill_id}' was a MANDATORY requirement of "
            f"project(s): {', '.join(usage['mandatory'])}. These "
            "requirements were removed, which changes feasibility of future "
            "runs; previous results may no longer be valid.",
            "warning",
        )
    return flask.redirect(target)


@web_bp.get("/preferences")
def preferences_overview() -> str:
    """Displays cross-table preference matrix."""
    students = repositories.StudentRepository().list_all()
    projects = repositories.ProjectRepository().list_all()
    return flask.render_template(
        "preferences.html", students=students, projects=projects
    )


# -----------------------------------------------------------------------------
# Fixed Assignments & Reruns
# -----------------------------------------------------------------------------


@web_bp.get("/fixed-assignments")
def list_fixed_assignments() -> str:
    """Lists administrative pre-allocated constraints."""
    fixed = repositories.FixedAssignmentRepository().list_all()
    students = repositories.StudentRepository().list_all()
    projects = repositories.ProjectRepository().list_all()
    return flask.render_template(
        "fixed_assignments.html",
        fixed_assignments=fixed,
        students=students,
        projects=projects,
    )


@web_bp.post("/fixed-assignments/new")
def create_fixed_assignment() -> flask.Response:
    """Locks a student to a designated project."""
    target = flask.url_for("visualization_web.list_fixed_assignments")
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied.", "danger")
        return flask.redirect(target)

    s_id = flask.request.form.get("student_id", "").strip()
    p_id = flask.request.form.get("project_id", "").strip()
    reason = flask.request.form.get("reason", "").strip()
    status = flask.request.form.get("status", "APPROVED").strip()

    if not s_id or not p_id:
        flask.flash("Student and Project must be selected.", "warning")
        return flask.redirect(target)

    repositories.FixedAssignmentRepository().save(
        models.FixedAssignment(
            student_id=s_id, project_id=p_id, status=status, reason=reason
        )
    )
    flask.flash(
        f"Fixed assignment created: Student {s_id} locked to Project {p_id}. "
        "A new run is required to recalculate allocations.",
        "success",
    )
    return flask.redirect(target)


@web_bp.post("/fixed-assignments/<student_id>/delete")
def delete_fixed_assignment(student_id: str) -> flask.Response:
    """Removes a locked allocation."""
    target = flask.url_for("visualization_web.list_fixed_assignments")
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied.", "danger")
        return flask.redirect(target)

    repositories.FixedAssignmentRepository().delete(student_id)
    flask.flash(f"Fixed assignment for student '{student_id}' removed.", "info")
    return flask.redirect(target)


# -----------------------------------------------------------------------------
# Scenarios & Data Seeding
# -----------------------------------------------------------------------------


@web_bp.get("/scenarios")
def scenarios_page() -> str:
    """Displays benchmark scenarios loader."""
    return flask.render_template("scenarios.html")


@web_bp.post("/load-scenario/<scenario_name>")
def load_scenario(scenario_name: str) -> flask.Response:
    """Populates database with a designated reproducible benchmark cohort."""
    repo_run = repositories.RunRepository()
    repo_run.clear_all_cohort_data()

    if scenario_name == "standard":
        data = demo_data.get_standard_scenario()
    elif scenario_name == "fixed":
        data = demo_data.get_fixed_assignment_scenario()
    elif scenario_name == "infeasible":
        data = demo_data.get_infeasible_scenario()
    elif scenario_name == "conflicting":
        data = demo_data.get_conflicting_fixed_scenario()
    else:
        flask.flash(f"Unknown scenario: '{scenario_name}'.", "warning")
        return flask.redirect(flask.url_for("visualization_web.scenarios_page"))

    skill_repo = repositories.SkillRepository()
    for s in data["skills"]:
        skill_repo.save(s)

    proj_repo = repositories.ProjectRepository()
    for p in data["projects"]:
        proj_repo.save(p)

    stud_repo = repositories.StudentRepository()
    for st in data["students"]:
        stud_repo.save(st)

    fixed_repo = repositories.FixedAssignmentRepository()
    for fa in data.get("fixed_assignments", []):
        fixed_repo.save(fa)

    flask.flash(
        f"Benchmark '{data['scenario_name']}' loaded successfully! "
        f"{data['description']}",
        "success",
    )
    return flask.redirect(flask.url_for("visualization_web.dashboard"))


@web_bp.post("/clear-data")
def clear_data() -> flask.Response:
    """Clears all cohort and constraint data."""
    repositories.RunRepository().clear_all_cohort_data()
    flask.flash("All cohort data cleared.", "info")
    return flask.redirect(flask.url_for("visualization_web.dashboard"))


# -----------------------------------------------------------------------------
# Runs & Solutions
# -----------------------------------------------------------------------------


@web_bp.post("/runs/trigger")
def trigger_run() -> flask.Response:
    """Submits current cohort data to Service A to generate allocations."""
    if not auth.can_trigger_optimization():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(flask.url_for("visualization_web.dashboard"))

    max_alts = int(flask.request.form.get("max_alternatives", 3))
    strat = flask.request.form.get("primary_strategy", "PREFERENCE")

    students = repositories.StudentRepository().list_all()
    projects = repositories.ProjectRepository().list_all()
    skills = repositories.SkillRepository().list_all()
    fixed = repositories.FixedAssignmentRepository().list_all()

    engine: contract.AssignmentEngineContract = solvers.AssignmentEngine()
    req = contract.RunRequest(
        students=students,
        projects=projects,
        skills=skills,
        fixed_assignments=fixed,
        strategy_key=strat,
        max_alternatives=max_alts,
    )
    val_outcome = engine.validate_inputs(req)
    for warning_msg in val_outcome.warnings:
        flask.flash(f"Warning: {warning_msg}", "warning")
    try:
        run = engine.execute_run(req)
    except NotImplementedError:
        flask.flash(
            "Notice: AssignmentEngine.execute_run() is not yet implemented by "
            "Team B. Running with MockAssignmentEngine for demonstration.",
            "info",
        )
        mock_engine = mocks.MockAssignmentEngine()
        run = mock_engine.execute_run(req)

    if run.status == "COMPLETED":
        flask.flash(
            f"Optimization run completed! Found {len(run.solutions)} "
            "distinct alternative solutions.",
            "success",
        )
    elif run.status == "INFEASIBLE":
        flask.flash(
            "Solver could not find a feasible solution under the specified "
            "hard constraints. Inspect diagnostics below.",
            "warning",
        )
    else:
        flask.flash(f"Run ended with status: {run.status}.", "danger")

    return flask.redirect(
        flask.url_for("visualization_web.view_run", run_id=run.id)
    )


@web_bp.get("/runs/<run_id>")
def view_run(run_id: str) -> Any:
    """Displays results, alternative solutions, and diagnostics of a run."""
    run = repositories.RunRepository().get_run(run_id)
    if not run:
        flask.flash(f"Run '{run_id}' not found.", "danger")
        return flask.redirect(flask.url_for("visualization_web.dashboard"))

    recs = recommendations.generate_recommendations(run.solutions)

    return flask.render_template(
        "run_detail.html",
        run=run,
        recommendations=recs,
    )


@web_bp.get("/solutions/<solution_id>")
def view_solution(solution_id: str) -> Any:
    """Displays complete student assignment details for a solution."""
    repo = repositories.RunRepository()
    solution = repo.get_solution(solution_id)
    if not solution:
        flask.flash(f"Solution '{solution_id}' not found.", "danger")
        return flask.redirect(flask.url_for("visualization_web.dashboard"))

    run = repo.get_run(solution.run_id)
    students = {s.id: s for s in repositories.StudentRepository().list_all()}
    projects = {p.id: p for p in repositories.ProjectRepository().list_all()}

    return flask.render_template(
        "solution_detail.html",
        solution=solution,
        run=run,
        students=students,
        projects=projects,
    )


@web_bp.post("/solutions/<solution_id>/lock-and-rerun")
def lock_and_rerun(solution_id: str) -> flask.Response:
    """Locks a student assignment from a solution and triggers a new run."""
    student_id = flask.request.form.get("student_id")
    project_id = flask.request.form.get("project_id")

    if not student_id or not project_id:
        flask.flash("Student and Project required.", "warning")
        return flask.redirect(
            flask.url_for(
                "visualization_web.view_solution", solution_id=solution_id
            )
        )

    # Persist as fixed assignment
    fixed_repo = repositories.FixedAssignmentRepository()
    fixed_repo.save(
        models.FixedAssignment(
            student_id=student_id,
            project_id=project_id,
            status="APPROVED",
            reason=f"Locked interactively from Solution {solution_id[:8]}.",
        )
    )

    # Immediately trigger rerun via Component B (Assignment Engine)
    students = repositories.StudentRepository().list_all()
    projects = repositories.ProjectRepository().list_all()
    skills = repositories.SkillRepository().list_all()
    fixed = fixed_repo.list_all()

    engine: contract.AssignmentEngineContract = solvers.AssignmentEngine()
    req = contract.RunRequest(
        students=students,
        projects=projects,
        skills=skills,
        fixed_assignments=fixed,
    )
    try:
        new_run = engine.execute_run(req)
    except NotImplementedError:
        new_run = mocks.MockAssignmentEngine().execute_run(req)

    flask.flash(
        f"Student {student_id} locked to Project {project_id}. "
        "New run generated!",
        "success",
    )
    return flask.redirect(
        flask.url_for("visualization_web.view_run", run_id=new_run.id)
    )

@web_bp.post("/clear-solutions")
def clear_solutions() -> flask.Response:
    """Clears all solutions in the current run."""
    repositories.RunRepository().clear_all_current_solutions()
    flask.flash("All solutions cleared.", "info")
    return flask.redirect(flask.url_for("visualization_web.dashboard"))

# -----------------------------------------------------------------------------
# Comparison & Recommendations
# -----------------------------------------------------------------------------


def _solution_option(
    solution: models.Solution, created_at: str = ""
) -> dict[str, Any]:
    """Builds a label-ready dropdown entry for a solution.

    Args:
        solution: Solution to describe (assignments are not needed).
        created_at: ISO timestamp of the parent run, if known.

    Returns:
        A dict with the keys "id", "run_id", "alternative_number" and
        "label".
    """
    run_part = f"Run {solution.run_id[:8]}"
    if created_at:
        run_part += f", {created_at[:16].replace('T', ' ')}"
    return {
        "id": solution.id,
        "run_id": solution.run_id,
        "alternative_number": solution.alternative_number,
        "label": (
            f"Alt #{solution.alternative_number} - "
            f"{solution.strategy_name} ({run_part})"
        ),
    }


def _build_solution_options(
    runs: list[models.AssignmentRun],
) -> list[dict[str, Any]]:
    """Flattens runs into dropdown entries, keeping the order of the runs.

    Args:
        runs: Runs ordered newest first, as returned by the repository.

    Returns:
        One entry per solution, newest run first and by alternative number
        within a run.
    """
    return [
        _solution_option(sol, run.created_at)
        for run in runs
        for sol in run.solutions
    ]


def _pick_default_partner(
    solution_id: str, options: list[dict[str, Any]]
) -> str | None:
    """Picks another alternative of the same run to compare against.

    Args:
        solution_id: Identifier of the already chosen solution.
        options: Dropdown entries as built by _build_solution_options().

    Returns:
        The ID of the next alternative of the same run (or the first other
        one if it is the last), or None if there is no other alternative.
    """
    chosen = next((o for o in options if o["id"] == solution_id), None)
    if chosen is None:
        return None
    siblings = [
        o
        for o in options
        if o["run_id"] == chosen["run_id"] and o["id"] != solution_id
    ]
    later = [
        o
        for o in siblings
        if o["alternative_number"] > chosen["alternative_number"]
    ]
    candidates = later or siblings
    return candidates[0]["id"] if candidates else None


def _ensure_run_options(
    solution_id: str,
    options: list[dict[str, Any]],
    run_repo: repositories.RunRepository,
) -> None:
    """Appends the run of a solution to the options if it is missing.

    This keeps links to solutions older than the dropdown window working.

    Args:
        solution_id: Requested solution identifier (may be empty/unknown).
        options: Dropdown entries, extended in place.
        run_repo: Repository used to look up the solution and its run.
    """
    if not solution_id or any(o["id"] == solution_id for o in options):
        return
    solution = run_repo.get_solution(solution_id)
    if solution is None:
        return
    run = run_repo.get_run(solution.run_id)
    if run is not None:
        options.extend(
            _solution_option(s, run.created_at) for s in run.solutions
        )


def _rank_label(rank: int | None) -> str:
    """Formats a preference rank for display.

    Args:
        rank: Preference rank, or None for an unranked assignment.

    Returns:
        "Unranked" or "Choice #<rank>".
    """
    return "Unranked" if rank is None else f"Choice #{rank}"


def _describe_rank_shift(
    rank_a: int | None, rank_b: int | None
) -> tuple[str, str]:
    """Describes how a student's preference rank changed between solutions.

    Args:
        rank_a: Rank in solution A (None if unranked).
        rank_b: Rank in solution B (None if unranked).

    Returns:
        A tuple of (text, badge_suffix) where badge_suffix is one of
        "success", "danger" or "secondary".
    """
    if rank_a is None and rank_b is None:
        return "Both unranked", "secondary"
    if rank_a is None:
        return "Ranked in B (was unranked)", "success"
    if rank_b is None:
        return "Unranked in B", "danger"
    delta = rank_b - rank_a
    steps = f"{abs(delta)} rank{'' if abs(delta) == 1 else 's'}"
    if delta < 0:
        return f"\u25b2 {steps} better", "success"
    if delta > 0:
        return f"\u25bc {steps} worse", "danger"
    return "Lateral move", "secondary"


def _enrich_changed_assignments(
    changed: list[dict[str, Any]],
    students: dict[str, models.Student],
    projects: dict[str, models.Project],
) -> list[dict[str, Any]]:
    """Adds display names, titles and rank labels to changed assignments.

    The engine's dictionaries are copied, never modified.

    Args:
        changed: The changed_assignments of a RunComparison.
        students: Map of student ID to Student.
        projects: Map of project ID to Project.

    Returns:
        New dicts with real student names and project titles (falling back
        to the IDs), "rank_a_label"/"rank_b_label", and "shift_text" /
        "shift_class" describing the rank shift.
    """
    enriched: list[dict[str, Any]] = []
    for item in changed:
        row = dict(item)
        student_id = item.get("student_id", "")
        student = students.get(student_id)
        row["student_name"] = student.display_name if student else student_id
        for side in ("a", "b"):
            project_id = item.get(f"project_{side}_id", "")
            project = projects.get(project_id)
            row[f"project_{side}_title"] = (
                project.title if project else project_id
            )
            row[f"rank_{side}_label"] = _rank_label(item.get(f"rank_{side}"))
        row["shift_text"], row["shift_class"] = _describe_rank_shift(
            item.get("rank_a"), item.get("rank_b")
        )
        enriched.append(row)
    return enriched


def _compare_via_contract(
    solution_a_id: str, solution_b_id: str
) -> models.RunComparison:
    """Compares two solutions via the engine, falling back to the mock.

    Args:
        solution_a_id: Identifier of the baseline solution.
        solution_b_id: Identifier of the comparison solution.

    Returns:
        The RunComparison produced by the engine or the mock engine.

    Raises:
        KeyError: If either solution cannot be found.
    """
    engine: contract.AssignmentEngineContract = solvers.AssignmentEngine()
    try:
        return engine.compare_solutions(solution_a_id, solution_b_id)
    except NotImplementedError:
        return mocks.MockAssignmentEngine().compare_solutions(
            solution_a_id, solution_b_id
        )


@web_bp.get("/compare")
def compare_solutions() -> Any:
    """Renders side-by-side comparative analysis of two solutions."""
    run_repo = repositories.RunRepository()
    options = _build_solution_options(
        run_repo.list_runs(limit=_COMPARE_RUN_LIMIT)
    )
    sol1 = flask.request.args.get("sol1", "").strip()
    sol2 = flask.request.args.get("sol2", "").strip()
    _ensure_run_options(sol1, options, run_repo)
    _ensure_run_options(sol2, options, run_repo)

    if sol1 and not sol2:
        sol2 = _pick_default_partner(sol1, options) or ""
        if not sol2 and any(o["id"] == sol1 for o in options):
            flask.flash(
                "This run has only one alternative, so there is nothing "
                "to compare it with.",
                "info",
            )
    elif sol2 and not sol1:
        flask.flash("Select a baseline solution (A) to compare with.", "info")

    by_id = {o["id"]: o for o in options}
    comparison: models.RunComparison | None = None
    if sol1 and sol2:
        try:
            comparison = _compare_via_contract(sol1, sol2)
        except KeyError as exc:
            reason = exc.args[0] if exc.args else "unknown solution"
            flask.flash(f"Cannot compare: {reason}", "danger")
        else:
            students = {
                s.id: s for s in repositories.StudentRepository().list_all()
            }
            projects = {
                p.id: p for p in repositories.ProjectRepository().list_all()
            }
            comparison = dataclasses.replace(
                comparison,
                changed_assignments=_enrich_changed_assignments(
                    comparison.changed_assignments, students, projects
                ),
            )
            if sol1 == sol2:
                flask.flash(
                    "Solutions A and B are identical, so no allocation "
                    "differs.",
                    "info",
                )
            elif (
                sol1 in by_id
                and sol2 in by_id
                and by_id[sol1]["run_id"] != by_id[sol2]["run_id"]
            ):
                flask.flash(
                    "These solutions come from different runs; their inputs "
                    "may differ, so deltas are not like-for-like.",
                    "warning",
                )

    return flask.render_template(
        "compare.html",
        all_solutions=options,
        sol_a=by_id.get(sol1),
        sol_b=by_id.get(sol2),
        comparison=comparison,
    )


@web_bp.get("/recommendations/<run_id>")
def view_recommendations(run_id: str) -> Any:
    """Displays transparent recommendations with evidence and advice."""
    run = repositories.RunRepository().get_run(run_id)
    if not run:
        flask.flash(f"Run '{run_id}' not found.", "danger")
        return flask.redirect(flask.url_for("visualization_web.dashboard"))

    recs = recommendations.generate_recommendations(run.solutions)

    return flask.render_template(
        "recommendations.html",
        run=run,
        recommendations=recs,
    )
