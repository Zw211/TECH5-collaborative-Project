"""Form parsing and validation for Component A (Visualization).

Keeps request parsing out of the Flask routes so that the validation rules
can be unit tested without a web request or a database.
"""

from collections.abc import Iterable, Mapping

from app.domain import models, validation


class RunSettingsForm:
    """Parses dashboard settings and reuses the engine's validation rules."""

    def __init__(self, form: Mapping[str, str]) -> None:
        """Initialize the submitted dashboard fields.

        Args:
            form: Submitted strategy and alternative-count fields.
        """
        self._form = form
        self.errors: list[str] = []

    def to_settings(self) -> tuple[str, int] | None:
        """Return parsed settings, or None with validation errors.

        Returns:
            A strategy key and alternative count, or None when invalid.
            Invalid fields are recorded in ``errors`` on every call.
        """
        strategy = self._form.get("primary_strategy", "PREFERENCE")
        raw_count = self._form.get("max_alternatives", "").strip()
        try:
            count = int(raw_count)
        except ValueError:
            count = None
        result = validation.validate_run_settings(strategy, count)
        self.errors = result.errors
        if self.errors or count is None:
            return None
        return strategy, count


class StudentSkillsForm:
    """Parse student skill fields before saving a student."""

    def __init__(
        self, form: Mapping[str, str], skill_ids: Iterable[str]
    ) -> None:
        """Initialize submitted fields and the allowed skill catalogue.

        Args:
            form: Submitted student skill fields.
            skill_ids: Identifiers of skills accepted by the form.
        """
        self._form = form
        self._skill_ids = set(skill_ids)
        self.errors: list[str] = []

    def to_skills(self) -> dict[str, int] | None:
        """Return parsed skills, omitting blank and zero values.

        Returns:
            Skill IDs mapped to integer levels, or None when invalid.
            Each call replaces ``errors`` with the current diagnostics.
        """
        self.errors = []
        skills: dict[str, int] = {}
        for field, value in self._form.items():
            if not field.startswith("skill_"):
                continue
            skill_id = field[len("skill_") :]
            if skill_id not in self._skill_ids:
                self.errors.append(
                    f"Student profile references unknown skill '{skill_id}'."
                )
                continue
            raw = value.strip()
            if not raw:
                continue
            try:
                level = int(raw)
            except ValueError:
                self.errors.append(
                    f"Skill '{skill_id}': level must be a whole number."
                )
                continue
            if level == 0:
                continue
            if not 1 <= level <= 5:
                self.errors.append(
                    f"Skill '{skill_id}': level must be between 1 and 5."
                )
                continue
            skills[skill_id] = level

        if self.errors:
            return None
        return skills


class ProjectForm:
    """Parses and validates the project creation and edit form.

    The form submits one ``req_level_<skill_id>`` field per catalogued skill
    (0 or empty means the skill is not required) and a
    ``req_mand_<skill_id>`` checkbox that is only present when ticked.

    Attributes:
        errors: Validation messages collected by the last call to
            to_project(). Empty when the form is valid.
    """

    MIN_LEVEL = 1
    MAX_LEVEL = 5

    def __init__(
        self,
        form: Mapping[str, str],
        skill_ids: Iterable[str],
        project_id: str | None = None,
    ) -> None:
        """Initializes the form wrapper.

        Args:
            form: Submitted form fields (e.g. flask.request.form).
            skill_ids: Identifiers of the catalogued skills, in display order.
            project_id: Identifier of the project being edited. When given,
                it overrides the submitted ``id`` field, which is read-only
                on the edit form.
        """
        self._form = form
        self._skill_ids = list(skill_ids)
        self._project_id = project_id
        self.errors: list[str] = []

    def to_project(self) -> models.Project | None:
        """Builds a Project from the submitted fields.

        Returns:
            The parsed Project, or None if any field is invalid. The reasons
            are available in ``errors``.
        """
        self.errors = []
        project_id = (self._project_id or self._field("id")).strip()
        title = self._field("title").strip()
        if not project_id:
            self.errors.append("Project identifier is required.")
        if not title:
            self.errors.append("Project title is required.")

        min_cap = self._parse_int("min_capacity", "Minimum capacity", 0)
        max_cap = self._parse_int("max_capacity", "Maximum capacity", None)
        if min_cap is not None and min_cap < 0:
            self.errors.append("Minimum capacity cannot be negative.")
        if max_cap is not None and max_cap < 1:
            self.errors.append("Maximum capacity must be at least 1.")
        if min_cap is not None and max_cap is not None and min_cap > max_cap:
            self.errors.append(
                f"Minimum capacity ({min_cap}) cannot exceed maximum "
                f"capacity ({max_cap})."
            )

        requirements = self._parse_requirements(project_id)

        if self.errors:
            return None
        return models.Project(
            id=project_id,
            title=title,
            description=self._field("description").strip(),
            min_capacity=min_cap,
            max_capacity=max_cap,
            requirements=requirements,
        )

    def _field(self, name: str) -> str:
        """Returns a submitted field, or an empty string if missing."""
        return self._form.get(name) or ""

    def _parse_int(
        self, name: str, label: str, default: int | None
    ) -> int | None:
        """Parses a whole-number field, recording an error if invalid.

        Args:
            name: Form field name.
            label: Human-readable field name used in error messages.
            default: Value used when the field is empty, or None if the
                field is required.

        Returns:
            The parsed integer, or None if the field is missing or invalid.
        """
        raw = self._field(name).strip()
        if not raw:
            if default is None:
                self.errors.append(f"{label} is required.")
            return default
        try:
            return int(raw)
        except ValueError:
            self.errors.append(f"{label} must be a whole number.")
            return None

    def _parse_requirements(
        self, project_id: str
    ) -> list[models.ProjectRequirement]:
        """Parses the skill requirement matrix.

        Args:
            project_id: Identifier stored on each requirement.

        Returns:
            One requirement per skill with a level from 1 to 5.
        """
        requirements: list[models.ProjectRequirement] = []
        unknown_skill_ids: set[str] = set()
        for field in self._form:
            if field.startswith("req_level_"):
                skill_id = field[len("req_level_") :]
            elif field.startswith("req_mand_"):
                skill_id = field[len("req_mand_") :]
            else:
                continue
            if skill_id not in self._skill_ids:
                unknown_skill_ids.add(skill_id)
        for skill_id in sorted(unknown_skill_ids):
            self.errors.append(
                f"Project requirement references unknown skill '{skill_id}'."
            )

        for skill_id in self._skill_ids:
            raw = self._field(f"req_level_{skill_id}").strip() or "0"
            raw_mandatory = self._field(f"req_mand_{skill_id}").strip()
            if raw_mandatory not in ("", "1", "on"):
                self.errors.append(
                    f"Mandatory flag for skill '{skill_id}' must be an "
                    f"unchecked "
                    "or checked box (empty, '1', or 'on')."
                )
                continue
            is_mandatory = raw_mandatory in ("1", "on")
            try:
                level = int(raw)
            except ValueError:
                self.errors.append(
                    f"Required level for skill '{skill_id}' must be a whole "
                    "number."
                )
                continue

            if level == 0:
                if is_mandatory:
                    self.errors.append(
                        f"Skill '{skill_id}' is marked mandatory but has no "
                        "required level."
                    )
                continue
            if not self.MIN_LEVEL <= level <= self.MAX_LEVEL:
                self.errors.append(
                    f"Required level for skill '{skill_id}' must be between "
                    f"{self.MIN_LEVEL} and {self.MAX_LEVEL}."
                )
                continue

            requirements.append(
                models.ProjectRequirement(
                    project_id=project_id,
                    skill_id=skill_id,
                    minimum_level=level,
                    is_mandatory=is_mandatory,
                )
            )
        return requirements
