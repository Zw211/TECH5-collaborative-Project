"""BILP assignment strategies and engine orchestration skeleton for TECH5.

In compliance with Section 5 and Section 8 of the TECH5 specification,
Team B is responsible for proposing and implementing an approved assignment
method (e.g. Integer Linear Programming, heuristic search, or stable matching).

This module defines the abstract strategy base class and the AssignmentEngine
that implements AssignmentEngineContract.
"""

import abc
import dataclasses
import math
import time
import uuid
from typing import Any

import pulp

from app import config
from app.contract import contract
from app.domain import models, validation
from app.engine import metrics
from app.persistence import repositories


class AssignmentStrategy(abc.ABC):
    """Abstract Base Class for student-to-project allocation strategies.

    Team B should derive concrete strategy subclasses implementing specific
    objective functions (e.g. preference satisfaction, skill fit, balanced).
    """

    def __init__(self, name: str, description: str) -> None:
        """Initializes the strategy with descriptive metadata.

        Args:
            name: Machine-readable identifier for the strategy.
            description: Human-readable explanation of the objective function.
        """
        self.name = name
        self.description = description

    @abc.abstractmethod
    def calculate_cost_or_utility(
        self,
        student: models.Student,
        project: models.Project,
        max_preferences: int,
    ) -> float:
        """Compute the utility or cost of a student-project allocation.

        Args:
            student: The candidate student.
            project: The target semester project.
            max_preferences: Maximum number of preferences ranked in cohort.

        Returns:
            Numerical weight reflecting desirability in optimization objective.
        """

    def solve(
        self,
        students: list[models.Student],
        projects: list[models.Project],
        fixed_assignments: list[models.FixedAssignment] | None = None,
        excluded_solutions: list[list[tuple[str, str]]] | None = None,
    ) -> tuple[str, list[models.Assignment], float | None, dict[str, Any]]:
        """Find one full allocation satisfying the confirmed hard constraints.

        Maximize this strategy's utility while preserving all hard constraints.
        A verified incumbent can be returned without proven optimality; inspect
        diagnostics["optimality_proven"] before claiming an optimal result.

        Args:
            students: Complete cohort of students.
            projects: Projects with capacities and team skill requirements.
            fixed_assignments: Active administrative locks of every status.
            excluded_solutions: Complete allocations to exclude from this solve.

        Returns:
            Status, verified assignments, objective value, and diagnostics.
            Statuses: FEASIBLE, INFEASIBLE, INVALID_INPUT, NOT_SOLVED, FAILED.
            A feasible result does not claim preference or skill optimality.
        """
        locks = fixed_assignments or []
        checked = validation.validate_cohort(
            students, projects, fixed_assignments=locks
        )
        diagnostics = contract.DiagnosticInfo().to_dict()
        diagnostics.update(
            errors=list(checked.errors),
            warnings=list(checked.warnings),
            infeasibility_reasons=list(checked.infeasibility_reasons),
            objective_mode=self.name,
            optimality_proven=False,
            metrics_computed=False,
            solver_version=pulp.__version__,
        )
        structural_errors = [
            error
            for error in checked.errors
            if error not in checked.infeasibility_reasons
        ]
        if not checked.is_valid or not checked.is_feasible:
            status = "INVALID_INPUT" if structural_errors else "INFEASIBLE"
            diagnostics["solver_status"] = "NOT_RUN"
            return status, [], None, diagnostics

        try:
            exclusions = _validate_exclusions(
                excluded_solutions, students, projects
            )
        except ValueError as error:
            diagnostics["solver_status"] = "NOT_RUN"
            diagnostics["errors"].append(str(error))
            return "INVALID_INPUT", [], None, diagnostics
        problem, variables = _build_feasibility_model(students, projects, locks)
        for allocation in exclusions:
            # Exact allocation means at least one of these pairs must change.
            problem += pulp.lpSum(variables[pair] for pair in allocation) <= (
                len(students) - 1
            )
        diagnostics["excluded_solutions_count"] = len(exclusions)
        max_preferences = max(len(student.preferences) for student in students)
        utilities = {
            (student.id, project.id): self.calculate_cost_or_utility(
                student, project, max_preferences
            )
            for student in students
            for project in projects
        }
        problem.setObjective(
            pulp.lpSum(
                utilities[pair] * variable
                for pair, variable in variables.items()
            )
        )
        diagnostics["max_preferences"] = max_preferences
        diagnostics["variables_count"] = len(variables)
        diagnostics["constraints_count"] = len(problem.constraints)
        diagnostics["time_limit_seconds"] = (
            config.Config.PULP_TIME_LIMIT_SECONDS
        )
        started = time.perf_counter()
        try:
            problem.solve(
                pulp.PULP_CBC_CMD(
                    msg=False, timeLimit=config.Config.PULP_TIME_LIMIT_SECONDS
                )
            )
        except (pulp.PulpSolverError, OSError) as error:
            diagnostics["solver_status"] = "ERROR"
            diagnostics["errors"].append(str(error))
            return "FAILED", [], None, diagnostics
        finally:
            diagnostics["solve_time_seconds"] = time.perf_counter() - started

        diagnostics["solver_status"] = pulp.LpStatus[problem.status]
        diagnostics["solution_status"] = pulp.LpSolution[problem.sol_status]
        if problem.status == pulp.LpStatusInfeasible:
            diagnostics["infeasibility_reasons"].append(
                "CBC proved no allocation remains after exclusions."
                if exclusions
                else "CBC proved the hard constraints infeasible."
            )
            return "INFEASIBLE", [], None, diagnostics
        if problem.status == pulp.LpStatusUnbounded:
            diagnostics["errors"].append("Unexpected unbounded binary model.")
            return "FAILED", [], None, diagnostics
        # CBC can report Optimal with an integer incumbent after interruption.
        # Retain both statuses; read only an explicitly reported solution.
        if problem.sol_status not in (
            pulp.LpSolutionOptimal,
            pulp.LpSolutionIntegerFeasible,
        ):
            diagnostics["warnings"].append(
                "No verified solution was obtained; the solver may have hit "
                "its time limit or stopped for another reason."
            )
            return "NOT_SOLVED", [], None, diagnostics
        if problem.sol_status != pulp.LpSolutionOptimal:
            diagnostics["warnings"].append(
                "Solver stopped with an incumbent; optimality is not proven."
            )
        try:
            assignments = _extract_assignments(variables, students, locks)
            _verify_assignment(students, projects, locks, assignments)
            pairs = frozenset((a.student_id, a.project_id) for a in assignments)
            if pairs in exclusions:
                raise ValueError("Solver returned an excluded assignment.")
        except ValueError as error:
            diagnostics["errors"].append(str(error))
            return "FAILED", [], None, diagnostics
        project_by_id = {project.id: project for project in projects}
        student_by_id = {student.id: student for student in students}
        for assignment in assignments:
            fit, unmet = metrics.calculate_assignment_skill_fit(
                student_by_id[assignment.student_id],
                project_by_id[assignment.project_id],
            )
            assignment.skill_fit_score = fit
            assignment.unmet_requirements = unmet
        # Sum the verified discrete choices, including a valid all-zero score.
        objective = sum(
            utilities[a.student_id, a.project_id] for a in assignments
        )
        diagnostics["assignment_verified"] = True
        diagnostics["assignment_skill_fit_computed"] = True
        diagnostics["optimality_proven"] = (
            problem.status == pulp.LpStatusOptimal
            and problem.sol_status == pulp.LpSolutionOptimal
        )
        return "FEASIBLE", assignments, objective, diagnostics


def _validate_exclusions(
    excluded_solutions: list[list[tuple[str, str]]] | None,
    students: list[models.Student],
    projects: list[models.Project],
) -> list[frozenset[tuple[str, str]]]:
    """Validate complete allocations with known IDs; deduplicate cuts."""
    if excluded_solutions is None:
        return []
    if not isinstance(excluded_solutions, list):
        raise ValueError("Excluded solutions must be a list of allocations.")
    student_ids = {student.id for student in students}
    project_ids = {project.id for project in projects}
    exclusions = []
    for allocation in excluded_solutions:
        if not isinstance(allocation, list) or len(allocation) != len(students):
            raise ValueError("Each exclusion must allocate every student once.")
        seen = set()
        for pair in allocation:
            if (
                not isinstance(pair, tuple)
                or len(pair) != 2
                or not all(isinstance(value, str) for value in pair)
            ):
                raise ValueError("Excluded pairs must be two string IDs.")
            student_id, project_id = pair
            if (
                student_id not in student_ids
                or project_id not in project_ids
                or student_id in seen
            ):
                raise ValueError("Unknown ID or repeated student in exclusion.")
            seen.add(student_id)
        canonical = frozenset(allocation)
        if canonical not in exclusions:
            exclusions.append(canonical)
    return exclusions


def _generate_alternatives(
    strategy: AssignmentStrategy,
    students: list[models.Student],
    projects: list[models.Project],
    fixed_assignments: list[models.FixedAssignment] | None = None,
    max_alternatives: int = 3,
) -> tuple[
    list[tuple[list[models.Assignment], float | None, dict[str, Any]]],
    dict[str, Any],
]:
    """Repeat one strategy with cuts, retaining verified distinct results.

    Returns raw assignment/score/diagnostic tuples for later engine integration,
    plus search diagnostics. Stops on K, proven exhaustion, or interruption.
    Retain a nonoptimal incumbent, then stop without claiming best-K results.
    Each solve has its own configured time limit.
    """
    search: dict[str, Any] = {
        "requested_count": max_alternatives,
        "returned_count": 0,
        "attempts": [],
        "stop_reason": "INVALID_INPUT",
    }
    settings = validation.validate_run_settings(strategy.name, max_alternatives)
    if not settings.is_valid:
        search["errors"] = settings.errors
        return [], search
    results = []
    exclusions: list[list[tuple[str, str]]] = []
    seen: set[frozenset[tuple[str, str]]] = set()
    for _ in range(max_alternatives):
        status, assignments, objective, info = strategy.solve(
            students, projects, fixed_assignments, exclusions
        )
        search["attempts"].append({"status": status, "diagnostics": info})
        if status != "FEASIBLE":
            search["stop_reason"] = (
                "EXHAUSTED" if status == "INFEASIBLE" and results else status
            )
            break
        pairs = frozenset((a.student_id, a.project_id) for a in assignments)
        if pairs in seen:
            search["stop_reason"] = "DUPLICATE"
            break
        results.append((assignments, objective, info))
        seen.add(pairs)
        exclusions.append(sorted(pairs))
        if not info.get("optimality_proven", False):
            search["stop_reason"] = "NON_OPTIMAL_INCUMBENT"
            break
    else:
        search["stop_reason"] = "K_REACHED"
    search["returned_count"] = len(results)
    return results, search


def _build_solution(
    run_id: str,
    alternative_number: int,
    strategy_name: str,
    students: list[models.Student],
    projects: list[models.Project],
    result: tuple[list[models.Assignment], float | None, dict[str, Any]],
    fixed_assignments: list[models.FixedAssignment] | None = None,
) -> models.Solution:
    """Convert a solver result into a verified solution without persistence.

    Every alternative must receive the same complete cohort so M is identical.
    Copy assignment metadata rather than mutating the solver result.
    """
    raw_assignments, objective, diagnostics = result
    locks = fixed_assignments or []
    _verify_assignment(students, projects, locks, raw_assignments)
    student_by_id = {s.id: s for s in students}
    project_by_id = {p.id: p for p in projects}
    fixed_pairs = {(lock.student_id, lock.project_id) for lock in locks}
    assignments = []
    for assignment in raw_assignments:
        student = student_by_id[assignment.student_id]
        project = project_by_id[assignment.project_id]
        fit, unmet = metrics.calculate_assignment_skill_fit(student, project)
        assignments.append(
            dataclasses.replace(
                assignment,
                preference_rank=student.get_preference_rank(project.id),
                skill_fit_score=fit,
                unmet_requirements=unmet,
                is_fixed=(student.id, project.id) in fixed_pairs,
            )
        )
    indicators = metrics.compute_solution_indicators(
        students, projects, assignments, locks
    )
    if not indicators["feasibility"]["is_feasible"]:
        raise ValueError(
            "Cannot create a feasible Solution from invalid assignments."
        )
    warnings = list(diagnostics.get("warnings", []))
    fair = indicators["fairness"]
    if fair["unranked_count"]:
        warnings.append(
            f"Numerical rank statistics use {fair['unranked_penalty']} (M+1) "
            "for unranked assignments; this is a penalty, not an actual rank."
        )
    if indicators["efficiency"]["individual_unmet_soft_requirements_count"]:
        warnings.append(
            "Soft gaps count individual student-project requirements, "
            "not unmet team-level requirements."
        )
    return models.Solution(
        id=str(uuid.uuid4()),
        run_id=run_id,
        alternative_number=alternative_number,
        strategy_name=strategy_name,
        objective_value=objective,
        assignments=assignments,
        indicators=indicators,
        warnings=warnings,
        diagnostics={**diagnostics, "metrics_computed": True},
    )


def _build_feasibility_model(
    students: list[models.Student],
    projects: list[models.Project],
    locks: list[models.FixedAssignment],
) -> tuple[pulp.LpProblem, dict[tuple[str, str], pulp.LpVariable]]:
    """Build the binary hard constraints without preference or skill scoring."""
    problem = pulp.LpProblem("assignment", pulp.LpMaximize)
    variables = {
        (student.id, project.id): pulp.LpVariable(f"x_{i}_{j}", cat="Binary")
        for i, student in enumerate(students)
        for j, project in enumerate(projects)
    }
    for student in students:
        problem += (
            pulp.lpSum(
                variables[student.id, project.id] for project in projects
            )
            == 1
        )
    for project in projects:
        headcount = pulp.lpSum(
            variables[student.id, project.id] for student in students
        )
        problem += headcount >= project.min_capacity
        problem += headcount <= project.max_capacity
        for requirement in project.requirements:
            if not requirement.is_mandatory:
                continue
            qualified_count = pulp.lpSum(
                variables[student.id, project.id]
                for student in students
                if student.get_skill_level(requirement.skill_id)
                >= requirement.minimum_level
            )
            # Positive headcount requires at least one qualified team member.
            # Empty optional projects need no coverage; positive minima remain.
            problem += headcount <= project.max_capacity * qualified_count
    for lock in locks:
        problem += variables[lock.student_id, lock.project_id] == 1
    return problem, variables


def _extract_assignments(
    variables: dict[tuple[str, str], pulp.LpVariable],
    students: list[models.Student],
    locks: list[models.FixedAssignment],
) -> list[models.Assignment]:
    """Check binary values and translate selected pairs to domain objects."""
    student_by_id = {student.id: student for student in students}
    fixed_pairs = {(lock.student_id, lock.project_id) for lock in locks}
    assignments = []
    for (student_id, project_id), variable in variables.items():
        value = variable.value()
        if (
            value is None
            or not math.isfinite(value)
            or min(abs(value), abs(value - 1)) > 1e-6
        ):
            raise ValueError(
                "Solver returned missing or nonbinary assignments."
            )
        if value > 0.5:
            assignments.append(
                models.Assignment(
                    student_id=student_id,
                    project_id=project_id,
                    is_fixed=(student_id, project_id) in fixed_pairs,
                    preference_rank=student_by_id[
                        student_id
                    ].get_preference_rank(project_id),
                )
            )
    return assignments


def _verify_assignment(
    students: list[models.Student],
    projects: list[models.Project],
    locks: list[models.FixedAssignment],
    assignments: list[models.Assignment],
) -> None:
    """Recheck the returned allocation independently of solver expressions."""
    student_by_id = {student.id: student for student in students}
    teams: dict[str, list[models.Student]] = {p.id: [] for p in projects}
    assigned: dict[str, str] = {}
    for assignment in assignments:
        if (
            assignment.student_id not in student_by_id
            or assignment.project_id not in teams
            or assignment.student_id in assigned
        ):
            raise ValueError(
                "Unknown reference or duplicate student assignment."
            )
        assigned[assignment.student_id] = assignment.project_id
        teams[assignment.project_id].append(
            student_by_id[assignment.student_id]
        )
    if set(assigned) != set(student_by_id):
        raise ValueError("Solver did not allocate every student exactly once.")
    for project in projects:
        team = teams[project.id]
        if not project.min_capacity <= len(team) <= project.max_capacity:
            raise ValueError(f"Capacity violation for project {project.id}.")
        for requirement in project.requirements:
            if (
                team
                and requirement.is_mandatory
                and not any(
                    student.get_skill_level(requirement.skill_id)
                    >= requirement.minimum_level
                    for student in team
                )
            ):
                raise ValueError(f"Mandatory skill missing for {project.id}.")
    for lock in locks:
        if assigned.get(lock.student_id) != lock.project_id:
            raise ValueError(f"Fixed assignment changed for {lock.student_id}.")


def _preference_utility(
    student: models.Student,
    project: models.Project,
    max_preferences: int,
) -> float:
    """Normalize rank using the longest preference list in this cohort."""
    rank = student.get_preference_rank(project.id)
    if rank is None or max_preferences == 0:
        return 0.0
    return (max_preferences - rank + 1) / max_preferences


class PreferenceOrientedSolver(AssignmentStrategy):
    """Maximize normalized preference satisfaction."""

    def __init__(self) -> None:
        """Set the existing preference strategy key."""
        super().__init__("PREFERENCE", "Maximize preference satisfaction")

    def calculate_cost_or_utility(
        self,
        student: models.Student,
        project: models.Project,
        max_preferences: int,
    ) -> float:
        """Return preference utility; unranked projects score zero."""
        return _preference_utility(student, project, max_preferences)


class SkillFitOrientedSolver(AssignmentStrategy):
    """Maximize average individual requirement fit across assigned pairs."""

    def __init__(self) -> None:
        """Set the existing skill-fit strategy key."""
        super().__init__("SKILL_FIT", "Maximize individual skill fit")

    def calculate_cost_or_utility(
        self,
        student: models.Student,
        project: models.Project,
        max_preferences: int,
    ) -> float:
        """Return capped proficiency-ratio fit from the shared metric."""
        fit, _ = metrics.calculate_assignment_skill_fit(student, project)
        return fit


class BalancedTradeoffSolver(AssignmentStrategy):
    """Give preference and skill-fit utility equal weight."""

    def __init__(self) -> None:
        """Set the existing balanced strategy key."""
        super().__init__("BALANCED", "Equal preference and skill-fit weights")

    def calculate_cost_or_utility(
        self,
        student: models.Student,
        project: models.Project,
        max_preferences: int,
    ) -> float:
        """Return half preference utility plus half individual skill fit."""
        preference = _preference_utility(student, project, max_preferences)
        fit, _ = metrics.calculate_assignment_skill_fit(student, project)
        return 0.5 * preference + 0.5 * fit


class AssignmentEngine(contract.AssignmentEngineContract):
    """Coordinate validation, assignment execution, and persistence.

    Implements the internal component contract (AssignmentEngineContract)
    connecting Component B to Component A.
    """

    def __init__(
        self, run_repo: repositories.RunRepository | None = None
    ) -> None:
        """Initializes the AssignmentEngine with persistence repositories.

        Args:
            run_repo: Optional repository for persisting runs and solutions.
        """
        self.run_repo = (
            run_repo if run_repo is not None else repositories.RunRepository()
        )
        self.strategies: dict[str, AssignmentStrategy] = {
            # Team B: Instantiate and register your custom strategies here
        }

    def validate_inputs(
        self, request: contract.RunRequest
    ) -> contract.ValidationOutcome:
        """Validates cohort and constraints before attempting optimization.

        Args:
            request: The run request containing students, projects, etc.

        Returns:
            ValidationOutcome with validity, feasibility, errors, and warnings.
        """
        val_result = validation.validate_cohort(
            students=request.students,
            projects=request.projects,
            skills=request.skills,
            fixed_assignments=request.fixed_assignments,
        )
        settings_result = validation.validate_run_settings(
            request.strategy_key, request.max_alternatives
        )
        val_result.errors.extend(settings_result.errors)
        if not settings_result.is_valid:
            val_result.is_valid = False
        return contract.ValidationOutcome(
            is_valid=val_result.is_valid,
            is_feasible=val_result.is_feasible,
            errors=list(val_result.errors),
            warnings=list(val_result.warnings),
            infeasibility_reasons=list(val_result.infeasibility_reasons),
        )

    def execute_run(self, request: contract.RunRequest) -> models.AssignmentRun:
        """Execute assignments and persist the resulting run.

        In accordance with Section 8 of the specification, Team B must:
        1. Synchronize entities to maintain relational integrity.
        2. Validate cohort feasibility.
        3. Generate one or more distinct assignment alternatives.
        4. Calculate indicators for each alternative using app.engine.metrics.
        5. Persist run and solutions via self.run_repo.
        6. Return populated models.AssignmentRun.

        Args:
            request: The run request containing students, projects, etc.

        Returns:
            The created AssignmentRun populated with alternative solutions.

        Raises:
            NotImplementedError: To be implemented by Team B.
        """
        raise NotImplementedError(
            "TODO (Team B): Implement execute_run in app/engine/solvers.py"
        )

    def run_assignment(
        self,
        students: list[models.Student],
        projects: list[models.Project],
        skills: list[models.Skill] | None = None,
        fixed_assignments: list[models.FixedAssignment] | None = None,
        strategy_name: str = "PREFERENCE",
        max_alternatives: int = 3,
        notes: str = "",
    ) -> models.AssignmentRun:
        """Convenience method delegating to execute_run via RunRequest.

        Args:
            students: Student profiles.
            projects: Project specifications.
            skills: Optional skills catalog.
            fixed_assignments: Optional pre-allocated locks.
            strategy_name: Strategy key name.
            max_alternatives: Max solutions to generate.
            notes: Administrative description or notes for the run.

        Returns:
            The created AssignmentRun.
        """
        req = contract.RunRequest(
            students=students,
            projects=projects,
            skills=skills,
            fixed_assignments=fixed_assignments or [],
            strategy_key=strategy_name,
            max_alternatives=max_alternatives,
            notes=notes,
        )
        return self.execute_run(req)

    def list_runs(self, limit: int = 20) -> list[models.AssignmentRun]:
        """Retrieves historical assignment runs from repository.

        Args:
            limit: Maximum number of runs to retrieve.

        Returns:
            List of historical AssignmentRun domain objects.
        """
        return self.run_repo.list_runs(limit=limit)

    def get_run(self, run_id: str) -> models.AssignmentRun | None:
        """Retrieves a specific run by identifier.

        Args:
            run_id: Unique run identifier.

        Returns:
            The AssignmentRun object, or None if not found.
        """
        return self.run_repo.get_run(run_id)

    def get_solution(self, solution_id: str) -> models.Solution | None:
        """Retrieves a specific solution and its student allocations.

        Args:
            solution_id: Unique solution identifier.

        Returns:
            The Solution object with assignments, or None if not found.
        """
        return self.run_repo.get_solution(solution_id)

    def compare_solutions(
        self, solution_a_id: str, solution_b_id: str
    ) -> models.RunComparison:
        """Compares two alternative solutions side-by-side using metrics module.

        Args:
            solution_a_id: Identifier of the baseline solution.
            solution_b_id: Identifier of the comparison solution.

        Returns:
            RunComparison containing delta metrics and changed assignments.

        Raises:
            KeyError: If either solution cannot be found.
        """
        sol_a = self.run_repo.get_solution(solution_a_id)
        sol_b = self.run_repo.get_solution(solution_b_id)
        if sol_a is None or sol_b is None:
            raise KeyError(
                f"Solutions not found: {solution_a_id}, {solution_b_id}"
            )
        comp_dict = metrics.compare_two_solutions(sol_a, sol_b)
        return models.RunComparison.from_dict(comp_dict)
