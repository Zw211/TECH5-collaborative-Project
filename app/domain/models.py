"""Domain entities and value objects for the TECH5 Assignment System.

This module defines the core data classes representing students, projects,
skills, preferences, fixed assignments, runs, solutions, and indicators.
"""

import dataclasses
import datetime
from typing import Any


@dataclasses.dataclass(frozen=True)
class Skill:
    """Represents a capability or competence required or possessed.

    Attributes:
        id: Unique identifier for the skill.
        name: Human-readable name of the skill.
        description: Detailed explanation of what the skill entails.
    """

    id: str
    name: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serializes the skill to a dictionary.

        Returns:
            Dictionary containing skill attributes.
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Skill":
        """Instantiates a Skill from dictionary data.

        Args:
            data: Dictionary representation of a skill.

        Returns:
            A new Skill instance.
        """
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data.get("description", "")),
        )


@dataclasses.dataclass(frozen=True)
class StudentSkill:
    """Associates a student with a demonstrated proficiency level in a skill.

    Attributes:
        student_id: Identifier of the student.
        skill_id: Identifier of the skill.
        level: Proficiency rating (typically 1 to 5, or binary 1).
    """

    student_id: str
    skill_id: str
    level: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Serializes the student skill to a dictionary.

        Returns:
            Dictionary containing student skill attributes.
        """
        return {
            "student_id": self.student_id,
            "skill_id": self.skill_id,
            "level": self.level,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StudentSkill":
        """Instantiates a StudentSkill from dictionary data.

        Args:
            data: Dictionary representation of a student skill.

        Returns:
            A new StudentSkill instance.
        """
        return cls(
            student_id=str(data["student_id"]),
            skill_id=str(data["skill_id"]),
            level=int(data.get("level", 1)),
        )


@dataclasses.dataclass(frozen=True)
class ProjectRequirement:
    """Represents a skill requirement demanded by a semester project.

    Attributes:
        project_id: Identifier of the project.
        skill_id: Identifier of the required skill.
        minimum_level: Minimum required skill proficiency level.
        is_mandatory: Whether this requirement must be strictly satisfied.
    """

    project_id: str
    skill_id: str
    minimum_level: int = 1
    is_mandatory: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serializes the requirement to a dictionary.

        Returns:
            Dictionary containing requirement attributes.
        """
        return {
            "project_id": self.project_id,
            "skill_id": self.skill_id,
            "minimum_level": self.minimum_level,
            "is_mandatory": self.is_mandatory,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectRequirement":
        """Instantiates a ProjectRequirement from dictionary data.

        Args:
            data: Dictionary representation of a requirement.

        Returns:
            A new ProjectRequirement instance.
        """
        return cls(
            project_id=str(data["project_id"]),
            skill_id=str(data["skill_id"]),
            minimum_level=int(data.get("minimum_level", 1)),
            is_mandatory=bool(data.get("is_mandatory", False)),
        )


@dataclasses.dataclass(frozen=True)
class Preference:
    """Represents a student's ranked preference for a specific project.

    Attributes:
        student_id: Identifier of the student.
        project_id: Identifier of the preferred project.
        rank: 1-indexed preference rank (1 = first choice, 2 = second choice).
    """

    student_id: str
    project_id: str
    rank: int

    def to_dict(self) -> dict[str, Any]:
        """Serializes the preference to a dictionary.

        Returns:
            Dictionary containing preference attributes.
        """
        return {
            "student_id": self.student_id,
            "project_id": self.project_id,
            "rank": self.rank,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Preference":
        """Instantiates a Preference from dictionary data.

        Args:
            data: Dictionary representation of a preference.

        Returns:
            A new Preference instance.
        """
        return cls(
            student_id=str(data["student_id"]),
            project_id=str(data["project_id"]),
            rank=int(data["rank"]),
        )


@dataclasses.dataclass
class Student:
    """Represents an individual student seeking project allocation.

    Attributes:
        id: Unique student identifier.
        display_name: Human-readable student name or anonymous identifier.
        skills: Mapping of skill IDs to proficiency levels.
        preferences: Ordered list of Preferences submitted by the student.
    """

    id: str
    display_name: str
    skills: dict[str, int] = dataclasses.field(default_factory=dict)
    preferences: list[Preference] = dataclasses.field(default_factory=list)

    def get_preference_rank(self, project_id: str) -> int | None:
        """Looks up the student's rank for a project.

        Args:
            project_id: The identifier of the project to check.

        Returns:
            The integer rank if preferred, or None if unranked.
        """
        for pref in self.preferences:
            if pref.project_id == project_id:
                return pref.rank
        return None

    def get_skill_level(self, skill_id: str) -> int:
        """Returns the student's proficiency level in a given skill.

        Args:
            skill_id: The skill identifier to query.

        Returns:
            The integer proficiency level, or 0 if not held.
        """
        return self.skills.get(skill_id, 0)

    def to_dict(self) -> dict[str, Any]:
        """Serializes the student entity to a dictionary.

        Returns:
            Dictionary containing student attributes.
        """
        return {
            "id": self.id,
            "display_name": self.display_name,
            "skills": dict(self.skills),
            "preferences": [p.to_dict() for p in self.preferences],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Student":
        """Creates a Student instance from a dictionary.

        Args:
            data: Dictionary with student attributes.

        Returns:
            A new Student instance.
        """
        student_id = str(data["id"])
        skills_raw = data.get("skills", {})
        skills_dict: dict[str, int] = {}
        if isinstance(skills_raw, dict):
            skills_dict = {str(k): int(v) for k, v in skills_raw.items()}
        elif isinstance(skills_raw, list):
            for item in skills_raw:
                if isinstance(item, dict):
                    skills_dict[str(item["skill_id"])] = int(
                        item.get("level", 1)
                    )
                else:
                    skills_dict[str(item)] = 1

        preferences_raw = data.get("preferences", [])
        preferences: list[Preference] = []
        for p in preferences_raw:
            if isinstance(p, dict):
                preferences.append(
                    Preference(
                        student_id=student_id,
                        project_id=str(p["project_id"]),
                        rank=int(p["rank"]),
                    )
                )
            else:
                preferences.append(
                    Preference(
                        student_id=student_id,
                        project_id=str(p),
                        rank=len(preferences) + 1,
                    )
                )

        return cls(
            id=student_id,
            display_name=str(data.get("display_name", student_id)),
            skills=skills_dict,
            preferences=preferences,
        )


@dataclasses.dataclass
class Project:
    """Represents a semester project with defined capacity and requirements.

    Attributes:
        id: Unique project identifier.
        title: Project title.
        description: Detailed summary of project scope.
        min_capacity: Minimum number of students needed to activate project.
        max_capacity: Maximum allowed student capacity.
        requirements: List of ProjectRequirement specifications.
    """

    id: str
    title: str
    description: str = ""
    min_capacity: int = 0
    max_capacity: int = 1
    requirements: list[ProjectRequirement] = dataclasses.field(
        default_factory=list
    )

    def to_dict(self) -> dict[str, Any]:
        """Serializes the project entity to a dictionary.

        Returns:
            Dictionary containing project attributes.
        """
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "min_capacity": self.min_capacity,
            "max_capacity": self.max_capacity,
            "requirements": [r.to_dict() for r in self.requirements],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        """Creates a Project instance from a dictionary.

        Args:
            data: Dictionary with project attributes.

        Returns:
            A new Project instance.
        """
        project_id = str(data["id"])
        requirements_raw = data.get("requirements", [])
        requirements: list[ProjectRequirement] = []
        for r in requirements_raw:
            if isinstance(r, dict):
                requirements.append(
                    ProjectRequirement(
                        project_id=project_id,
                        skill_id=str(r["skill_id"]),
                        minimum_level=int(r.get("minimum_level", 1)),
                        is_mandatory=bool(r.get("is_mandatory", False)),
                    )
                )
            else:
                requirements.append(
                    ProjectRequirement(
                        project_id=project_id,
                        skill_id=str(r),
                        minimum_level=1,
                        is_mandatory=False,
                    )
                )

        return cls(
            id=project_id,
            title=str(data.get("title", project_id)),
            description=str(data.get("description", "")),
            min_capacity=int(data.get("min_capacity", 0)),
            max_capacity=int(data.get("max_capacity", 1)),
            requirements=requirements,
        )


@dataclasses.dataclass(frozen=True)
class FixedAssignment:
    """Specifies a mandatory assignment constraint that must remain locked.

    Attributes:
        student_id: Identifier of the assigned student.
        project_id: Identifier of the designated project.
        status: Administrative state of the lock (e.g. APPROVED, MANDATORY).
        reason: Justification or note explaining the pre-allocation.
    """

    student_id: str
    project_id: str
    status: str = "APPROVED"
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serializes the fixed assignment to a dictionary.

        Returns:
            Dictionary containing fixed assignment attributes.
        """
        return {
            "student_id": self.student_id,
            "project_id": self.project_id,
            "status": self.status,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FixedAssignment":
        """Instantiates a FixedAssignment from dictionary data.

        Args:
            data: Dictionary representation of a fixed assignment.

        Returns:
            A new FixedAssignment instance.
        """
        return cls(
            student_id=str(data["student_id"]),
            project_id=str(data["project_id"]),
            status=str(data.get("status", "APPROVED")),
            reason=str(data.get("reason", "")),
        )


@dataclasses.dataclass
class Assignment:
    """An individual student-to-project allocation within a solution.

    Attributes:
        student_id: Identifier of the assigned student.
        project_id: Identifier of the assigned project.
        is_fixed: True if this assignment resulted from a fixed constraint.
        preference_rank: 1-based rank of the assignment, or None if unranked.
        skill_fit_score: Fractional score [0.0, 1.0] reflecting requirement fit.
        unmet_requirements: List of skill IDs required by the project but
            lacked by the student.
    """

    student_id: str
    project_id: str
    is_fixed: bool = False
    preference_rank: int | None = None
    skill_fit_score: float = 0.0
    unmet_requirements: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializes the assignment to a dictionary.

        Returns:
            Dictionary containing assignment attributes.
        """
        return {
            "student_id": self.student_id,
            "project_id": self.project_id,
            "is_fixed": self.is_fixed,
            "preference_rank": self.preference_rank,
            "skill_fit_score": round(self.skill_fit_score, 4),
            "unmet_requirements": list(self.unmet_requirements),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Assignment":
        """Creates an Assignment instance from dictionary data.

        Args:
            data: Dictionary representation of an assignment.

        Returns:
            A new Assignment instance.
        """
        return cls(
            student_id=str(data["student_id"]),
            project_id=str(data["project_id"]),
            is_fixed=bool(data.get("is_fixed", False)),
            preference_rank=data.get("preference_rank"),
            skill_fit_score=float(data.get("skill_fit_score", 0.0)),
            unmet_requirements=[
                str(req) for req in data.get("unmet_requirements", [])
            ],
        )


@dataclasses.dataclass
class Solution:
    """Represents a complete feasible allocation outcome.

    Attributes:
        id: Unique identifier of the solution.
        run_id: Identifier of the parent optimization run.
        alternative_number: 1-indexed solution order within the run.
        strategy_name: Name of the solver strategy producing this solution.
        objective_value: Numerical objective score calculated by the solver.
        assignments: List of student assignments in this solution.
        indicators: Calculated analytical metrics (efficiency, fairness, etc.).
        warnings: Non-fatal notices or trade-off warnings for decision makers.
        diagnostics: Additional operational solver data.
    """

    id: str
    run_id: str
    alternative_number: int
    strategy_name: str
    objective_value: float | None = None
    assignments: list[Assignment] = dataclasses.field(default_factory=list)
    indicators: dict[str, Any] = dataclasses.field(default_factory=dict)
    warnings: list[str] = dataclasses.field(default_factory=list)
    diagnostics: dict[str, Any] = dataclasses.field(default_factory=dict)

    def get_assignment_for_student(self, student_id: str) -> Assignment | None:
        """Retrieves assignment details for a specified student.

        Args:
            student_id: The identifier of the student to look up.

        Returns:
            The Assignment instance if assigned, otherwise None.
        """
        for assignment in self.assignments:
            if assignment.student_id == student_id:
                return assignment
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serializes the solution to a dictionary.

        Returns:
            Dictionary containing solution attributes and indicators.
        """
        return {
            "id": self.id,
            "run_id": self.run_id,
            "alternative_number": self.alternative_number,
            "strategy_name": self.strategy_name,
            "objective_value": self.objective_value,
            "assignments": [a.to_dict() for a in self.assignments],
            "indicators": dict(self.indicators),
            "warnings": list(self.warnings),
            "diagnostics": dict(self.diagnostics),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Solution":
        """Creates a Solution instance from dictionary data.

        Args:
            data: Dictionary representation of a solution.

        Returns:
            A new Solution instance.
        """
        assignments = [
            Assignment.from_dict(a) for a in data.get("assignments", [])
        ]
        return cls(
            id=str(data["id"]),
            run_id=str(data["run_id"]),
            alternative_number=int(data["alternative_number"]),
            strategy_name=str(data.get("strategy_name", "UNKNOWN")),
            objective_value=data.get("objective_value"),
            assignments=assignments,
            indicators=dict(data.get("indicators", {})),
            warnings=[str(w) for w in data.get("warnings", [])],
            diagnostics=dict(data.get("diagnostics", {})),
        )


@dataclasses.dataclass
class AssignmentRun:
    """Encapsulates a full optimization execution with historical context.

    Attributes:
        id: Unique identifier for the run.
        created_at: ISO 8601 timestamp string of execution start.
        status: Execution status (e.g. COMPLETED, INFEASIBLE, FAILED).
        configuration: Solver configuration dictionary.
        solutions: List of alternative Solution instances generated.
        diagnostics: High-level diagnostics and execution logs.
    """

    id: str
    created_at: str = dataclasses.field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )
    status: str = "PENDING"
    configuration: dict[str, Any] = dataclasses.field(default_factory=dict)
    solutions: list[Solution] = dataclasses.field(default_factory=list)
    diagnostics: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serializes the assignment run to a dictionary.

        Returns:
            Dictionary containing run attributes and solutions.
        """
        return {
            "id": self.id,
            "created_at": self.created_at,
            "status": self.status,
            "configuration": dict(self.configuration),
            "solutions": [s.to_dict() for s in self.solutions],
            "solution_count": len(self.solutions),
            "diagnostics": dict(self.diagnostics),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssignmentRun":
        """Creates an AssignmentRun instance from dictionary data.

        Args:
            data: Dictionary representation of an assignment run.

        Returns:
            A new AssignmentRun instance.
        """
        solutions = [Solution.from_dict(s) for s in data.get("solutions", [])]
        return cls(
            id=str(data["id"]),
            created_at=str(
                data.get(
                    "created_at",
                    datetime.datetime.now(datetime.timezone.utc).isoformat(),
                )
            ),
            status=str(data.get("status", "PENDING")),
            configuration=dict(data.get("configuration", {})),
            solutions=solutions,
            diagnostics=dict(data.get("diagnostics", {})),
        )


@dataclasses.dataclass
class RunComparison:
    """Represents a comparative trade-off analysis between two solutions.

    Attributes:
        solution_a_id: Unique identifier of baseline solution A.
        solution_a_alt: Alternative number of solution A.
        solution_b_id: Unique identifier of comparison solution B.
        solution_b_alt: Alternative number of solution B.
        delta_metrics: Calculated indicator deltas (solution B - solution A).
        changed_assignments: List of re-allocated students with rank deltas.
        changed_students_count: Count of students assigned different projects.
        total_students: Total student count in the evaluation cohort.
    """

    solution_a_id: str
    solution_a_alt: int
    solution_b_id: str
    solution_b_alt: int
    delta_metrics: dict[str, Any] = dataclasses.field(default_factory=dict)
    changed_assignments: list[dict[str, Any]] = dataclasses.field(
        default_factory=list
    )
    changed_students_count: int = 0
    total_students: int = 0
    is_distinct: bool = True
    rank_improved_count: int = 0
    rank_worsened_count: int = 0
    delta_mean_skill_fit: float = 0.0
    delta_mean_rank: float = 0.0
    delta_unranked_count: int = 0
    trade_off_summary: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializes the run comparison to a dictionary.

        Returns:
            Dictionary containing comparison metrics and re-allocations.
        """
        return {
            "solution_a_id": self.solution_a_id,
            "solution_a_alt": self.solution_a_alt,
            "solution_b_id": self.solution_b_id,
            "solution_b_alt": self.solution_b_alt,
            "delta_metrics": dict(self.delta_metrics),
            "changed_assignments": list(self.changed_assignments),
            "changed_students_count": self.changed_students_count,
            "total_students": self.total_students,
            "is_distinct": self.is_distinct,
            "rank_improved_count": self.rank_improved_count,
            "rank_worsened_count": self.rank_worsened_count,
            "delta_mean_skill_fit": self.delta_mean_skill_fit,
            "delta_mean_rank": self.delta_mean_rank,
            "delta_unranked_count": self.delta_unranked_count,
            "trade_off_summary": list(self.trade_off_summary),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunComparison":
        """Creates a RunComparison instance from dictionary data.

        Args:
            data: Dictionary representation of a run comparison.

        Returns:
            A new RunComparison instance.
        """
        return cls(
            solution_a_id=str(data.get("solution_a_id", "")),
            solution_a_alt=int(data.get("solution_a_alt", 1)),
            solution_b_id=str(data.get("solution_b_id", "")),
            solution_b_alt=int(data.get("solution_b_alt", 2)),
            delta_metrics=dict(data.get("delta_metrics", {})),
            changed_assignments=list(data.get("changed_assignments", [])),
            changed_students_count=int(data.get("changed_students_count", 0)),
            total_students=int(data.get("total_students", 0)),
            is_distinct=bool(data.get("is_distinct", True)),
            rank_improved_count=int(data.get("rank_improved_count", 0)),
            rank_worsened_count=int(data.get("rank_worsened_count", 0)),
            delta_mean_skill_fit=float(data.get("delta_mean_skill_fit", 0.0)),
            delta_mean_rank=float(data.get("delta_mean_rank", 0.0)),
            delta_unranked_count=int(data.get("delta_unranked_count", 0)),
            trade_off_summary=list(data.get("trade_off_summary", [])),
        )
