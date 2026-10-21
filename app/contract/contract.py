"""Internal component contract defining the Python interface for TECH5 DSS.

This module formalizes the Python-level agreement between Component A
(Visualization & Recommendation) and Component B (Assignment Engine).
"""

import abc
import dataclasses
import enum
from typing import Any

from app.domain import models


class RunStatus(enum.Enum):
    """Execution status values for assignment runs."""

    COMPLETED = "COMPLETED"
    INFEASIBLE = "INFEASIBLE"
    INVALID_INPUT = "INVALID_INPUT"
    WARNING = "WARNING"
    FAILED = "FAILED"


@dataclasses.dataclass(frozen=True)
class DiagnosticInfo:
    """Detailed analytical and mathematical diagnostics for an execution.

    Attributes:
        solver_status: The status reported by the optimization solver.
        solve_time_seconds: Elapsed time spent in optimization.
        constraints_count: Number of constraint rows generated in solver.
        variables_count: Number of decision variables in solver.
        infeasibility_reasons: List of identified root causes if infeasible.
        additional_info: Key-value diagnostics and engine telemetry.
    """

    solver_status: str = "NOT_SOLVED"
    solve_time_seconds: float = 0.0
    constraints_count: int = 0
    variables_count: int = 0
    infeasibility_reasons: list[str] = dataclasses.field(default_factory=list)
    additional_info: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serializes diagnostic info to dictionary.

        Returns:
            Dictionary containing diagnostic attributes.
        """
        return {
            "solver_status": self.solver_status,
            "solve_time_seconds": self.solve_time_seconds,
            "constraints_count": self.constraints_count,
            "variables_count": self.variables_count,
            "infeasibility_reasons": list(self.infeasibility_reasons),
            "additional_info": dict(self.additional_info),
        }


@dataclasses.dataclass(frozen=True)
class ValidationOutcome:
    """Structured result of input validation before starting a run.

    Attributes:
        is_valid: True if structural syntax and referential integrity pass.
        is_feasible: False if hard mathematical constraints cannot be met.
        errors: Fatal validation errors that reject input.
        warnings: Advisory messages for non-fatal conditions.
        infeasibility_reasons: Proof details when provably infeasible.
    """

    is_valid: bool = True
    is_feasible: bool = True
    errors: list[str] = dataclasses.field(default_factory=list)
    warnings: list[str] = dataclasses.field(default_factory=list)
    infeasibility_reasons: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializes validation outcome to dictionary.

        Returns:
            Dictionary representation of validation outcome.
        """
        return {
            "is_valid": self.is_valid,
            "is_feasible": self.is_feasible,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "infeasibility_reasons": list(self.infeasibility_reasons),
        }


@dataclasses.dataclass(frozen=True)
class RunRequest:
    """Structured request submitted to start an assignment run.

    Attributes:
        students: Cohort of students with skills and preferences.
        projects: Project catalog with capacity bounds and requirements.
        skills: Optional catalog of defined skills.
        fixed_assignments: Pre-allocated locks that must be enforced.
        strategy_key: Selected optimization strategy objective key.
        max_alternatives: Maximum number of distinct solutions to generate.
        notes: Administrative description or notes for the run.
    """

    students: list[models.Student]
    projects: list[models.Project]
    skills: list[models.Skill] | None = None
    fixed_assignments: list[models.FixedAssignment] | None = None
    strategy_key: str = "PREFERENCE"
    max_alternatives: int = 3
    notes: str = ""


class AssignmentEngineContract(abc.ABC):
    """Abstract contract interface for Component B (Assignment Engine).

    Component A (Visualization & Recommendation) interacts with Component B
    exclusively through this Python interface.
    """

    @abc.abstractmethod
    def validate_inputs(self, request: RunRequest) -> ValidationOutcome:
        """Validates cohort and constraints before attempting optimization.

        Args:
            request: The run request containing students, projects, etc.

        Returns:
            ValidationOutcome with validity, feasibility, errors, warnings.
        """

    @abc.abstractmethod
    def execute_run(self, request: RunRequest) -> models.AssignmentRun:
        """Execute assignments and persist the resulting run.

        Args:
            request: The run request containing students, projects, etc.

        Returns:
            The created AssignmentRun populated with alternative solutions.
        """

    @abc.abstractmethod
    def list_runs(self, limit: int = 20) -> list[models.AssignmentRun]:
        """Retrieves historical assignment runs.

        Args:
            limit: Maximum number of runs to retrieve.

        Returns:
            List of historical AssignmentRun domain objects.
        """

    @abc.abstractmethod
    def get_run(self, run_id: str) -> models.AssignmentRun | None:
        """Retrieves a specific run by identifier.

        Args:
            run_id: Unique run identifier.

        Returns:
            The AssignmentRun object, or None if not found.
        """

    @abc.abstractmethod
    def get_solution(self, solution_id: str) -> models.Solution | None:
        """Retrieves a specific solution and its student allocations.

        Args:
            solution_id: Unique solution identifier.

        Returns:
            The Solution object with assignments, or None if not found.
        """

    @abc.abstractmethod
    def compare_solutions(
        self, solution_a_id: str, solution_b_id: str
    ) -> models.RunComparison:
        """Compares two alternative solutions side-by-side.

        Args:
            solution_a_id: Identifier of the baseline solution.
            solution_b_id: Identifier of the comparison solution.

        Returns:
            RunComparison containing delta metrics and changed assignments.

        Raises:
            KeyError: If either solution cannot be found.
        """
