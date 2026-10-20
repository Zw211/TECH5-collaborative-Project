"""Mock implementation of AssignmentEngineContract for Week 1 unblocking.

This module provides a realistic mock AssignmentEngine that implements
AssignmentEngineContract, enabling Team A (Visualization & Recommendation)
to develop, visualize, compare, and test user workflows without waiting for
Team B to complete their mathematical optimization engine.
"""

import collections
import datetime
import uuid
from typing import Any

from app.contract import contract
from app.domain import models
from app.persistence import repositories


class MockAssignmentEngine(contract.AssignmentEngineContract):
    """Mock assignment engine returning pre-computed and synthetic solutions.

    Adheres strictly to the AssignmentEngineContract interface.
    """

    def __init__(
        self, run_repo: repositories.RunRepository | None = None
    ) -> None:
        """Initializes the mock engine with persistence support.

        Args:
            run_repo: Optional repository for persisting mock runs.
        """
        self.run_repo = (
            run_repo if run_repo is not None else repositories.RunRepository()
        )

    def validate_inputs(
        self, request: contract.RunRequest
    ) -> contract.ValidationOutcome:
        """Validates cohort and constraints synthetically.

        Args:
            request: The run request containing students, projects, etc.

        Returns:
            ValidationOutcome indicating feasibility and sanity.
        """
        if not request.students or not request.projects:
            return contract.ValidationOutcome(
                is_valid=True,
                is_feasible=False,
                errors=[],
                warnings=["Mock engine: Empty student cohort or project catalog."],
                infeasibility_reasons=["Cohort or project list is empty."],
            )

        total_students = len(request.students)
        total_capacity = sum(p.max_capacity for p in request.projects)

        if total_students > total_capacity:
            return contract.ValidationOutcome(
                is_valid=True,
                is_feasible=False,
                errors=[],
                warnings=[],
                infeasibility_reasons=[
                    f"Total students ({total_students}) exceed aggregate "
                    f"project capacity ({total_capacity})."
                ],
            )

        return contract.ValidationOutcome(
            is_valid=True,
            is_feasible=True,
            errors=[],
            warnings=["Mock validation passed (MockAssignmentEngine active)."],
            infeasibility_reasons=[],
        )

    def execute_run(
        self, request: contract.RunRequest
    ) -> models.AssignmentRun:
        """Generates synthetic multi-alternative solutions and persists them.

        Args:
            request: The run request containing students, projects, etc.

        Returns:
            The created AssignmentRun populated with mock alternative solutions.
        """
        run_id = str(uuid.uuid4())
        val_outcome = self.validate_inputs(request)

        if not val_outcome.is_feasible:
            run = models.AssignmentRun(
                id=run_id,
                created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                status=contract.RunStatus.INFEASIBLE.value,
                configuration={
                    "max_alternatives": request.max_alternatives,
                    "primary_strategy": request.strategy_key,
                    "engine": "MockAssignmentEngine",
                },
                solutions=[],
                diagnostics={
                    "solver_status": "INFEASIBLE",
                    "reasons": val_outcome.infeasibility_reasons,
                },
            )
            self.run_repo.save_run(run)
            return run

        # Synchronize entities to DB
        if request.skills:
            skill_repo = repositories.SkillRepository(self.run_repo.db)
            for sk in request.skills:
                skill_repo.save(sk)

        proj_repo = repositories.ProjectRepository(self.run_repo.db)
        for proj in request.projects:
            proj_repo.save(proj)

        stud_repo = repositories.StudentRepository(self.run_repo.db)
        for stud in request.students:
            stud_repo.save(stud)

        if request.fixed_assignments:
            fixed_repo = repositories.FixedAssignmentRepository(self.run_repo.db)
            for fa in request.fixed_assignments:
                fixed_repo.save(fa)

        # Build mock solutions
        solutions: list[models.Solution] = []
        num_alts = max(1, min(request.max_alternatives, 3))

        fixed_map = {
            fa.student_id: fa.project_id
            for fa in (request.fixed_assignments or [])
        }

        strategy_names = [
            request.strategy_key,
            "SKILL_FIT_MOCK",
            "BALANCED_MOCK",
        ]

        for alt_idx in range(num_alts):
            sol_id = str(uuid.uuid4())
            asgs: list[models.Assignment] = []
            proj_counts: dict[str, int] = collections.defaultdict(int)

            # Assign fixed students first
            assigned_students: set[str] = set()
            for stud in request.students:
                if stud.id in fixed_map:
                    target_p = fixed_map[stud.id]
                    rank = stud.get_preference_rank(target_p) or 1
                    asgs.append(
                        models.Assignment(
                            student_id=stud.id,
                            project_id=target_p,
                            is_fixed=True,
                            preference_rank=rank,
                            skill_fit_score=0.90,
                            unmet_requirements=[],
                        )
                    )
                    proj_counts[target_p] += 1
                    assigned_students.add(stud.id)

            # Assign remaining students with permutation based on alternative
            unassigned = [
                s for s in request.students if s.id not in assigned_students
            ]
            # Permute unassigned students for subsequent alternatives
            if alt_idx > 0 and len(unassigned) > 1:
                unassigned = unassigned[alt_idx:] + unassigned[:alt_idx]

            proj_list = list(request.projects)
            for i, stud in enumerate(unassigned):
                # Target project with available capacity
                chosen_proj = proj_list[(i + alt_idx) % len(proj_list)]
                rank = stud.get_preference_rank(chosen_proj.id)
                pref_rank = rank if rank is not None else 1
                skill_fit = 0.85 if alt_idx == 0 else 0.78 + (alt_idx * 0.05)

                asgs.append(
                    models.Assignment(
                        student_id=stud.id,
                        project_id=chosen_proj.id,
                        is_fixed=False,
                        preference_rank=pref_rank,
                        skill_fit_score=round(skill_fit, 2),
                        unmet_requirements=[],
                    )
                )
                proj_counts[chosen_proj.id] += 1

            # Synthetic indicators
            mean_fit = round(
                sum(a.skill_fit_score for a in asgs) / float(len(asgs)), 2
            )
            ranks = [
                a.preference_rank
                for a in asgs
                if a.preference_rank is not None
            ]
            mean_rank = (
                round(sum(ranks) / float(len(ranks)), 2) if ranks else 1.0
            )

            indicators: dict[str, Any] = {
                "feasibility": {
                    "is_feasible": True,
                    "violations": [],
                    "assigned_count": len(asgs),
                    "total_students": len(request.students),
                },
                "efficiency": {
                    "mean_skill_fit": mean_fit,
                    "unmet_soft_requirements_count": 0,
                    "total_skill_fit_sum": round(
                        sum(a.skill_fit_score for a in asgs), 2
                    ),
                },
                "fairness": {
                    "rank_distribution": {
                        f"rank_{r}": ranks.count(r) for r in sorted(set(ranks))
                    },
                    "unranked_count": 0,
                    "unranked_pct": 0.0,
                    "worst_rank": max(ranks) if ranks else 1,
                    "mean_rank": mean_rank,
                    "rank_variance": 0.25,
                    "rank_gini": 0.10 + (alt_idx * 0.03),
                },
                "capacity": {
                    "total_assigned": len(asgs),
                    "total_capacity": sum(p.max_capacity for p in request.projects),
                    "overall_utilization_pct": round(
                        len(asgs)
                        / float(sum(p.max_capacity for p in request.projects))
                        * 100.0,
                        1,
                    ),
                    "projects": {
                        p.id: {
                            "assigned_count": proj_counts[p.id],
                            "min_capacity": p.min_capacity,
                            "max_capacity": p.max_capacity,
                            "utilization_pct": round(
                                (proj_counts[p.id] / float(p.max_capacity) * 100.0)
                                if p.max_capacity > 0
                                else 0.0,
                                1,
                            ),
                        }
                        for p in request.projects
                    },
                },
            }

            strat_name = strategy_names[alt_idx % len(strategy_names)]
            sol = models.Solution(
                id=sol_id,
                run_id=run_id,
                alternative_number=alt_idx + 1,
                strategy_name=strat_name,
                objective_value=round(100.0 - (alt_idx * 5.0), 2),
                assignments=asgs,
                indicators=indicators,
                warnings=[],
                diagnostics={
                    "solver_status": "Optimal",
                    "note": "Generated by MockAssignmentEngine",
                },
            )
            solutions.append(sol)

        run = models.AssignmentRun(
            id=run_id,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            status=contract.RunStatus.COMPLETED.value,
            configuration={
                "max_alternatives": request.max_alternatives,
                "primary_strategy": request.strategy_key,
                "engine": "MockAssignmentEngine",
            },
            solutions=solutions,
            diagnostics={
                "solver_status": "Optimal",
                "solution_count": len(solutions),
                "message": "Mock run completed successfully.",
            },
        )
        self.run_repo.save_run(run)
        return run

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
        """Retrieves a specific solution by identifier.

        Args:
            solution_id: Unique solution identifier.

        Returns:
            The Solution object with assignments, or None if not found.
        """
        return self.run_repo.get_solution(solution_id)

    def compare_solutions(
        self, solution_a_id: str, solution_b_id: str
    ) -> models.RunComparison:
        """Compares two solutions side-by-side.

        Args:
            solution_a_id: Identifier of baseline solution A.
            solution_b_id: Identifier of comparison solution B.

        Returns:
            RunComparison with delta metrics and changed assignments.

        Raises:
            KeyError: If either solution is not found.
        """
        sol_a = self.run_repo.get_solution(solution_a_id)
        sol_b = self.run_repo.get_solution(solution_b_id)

        if sol_a is None or sol_b is None:
            raise KeyError(
                f"Solutions not found for comparison: {solution_a_id}, "
                f"{solution_b_id}"
            )

        map_a = {a.student_id: a for a in sol_a.assignments}
        map_b = {b.student_id: b for b in sol_b.assignments}

        changed: list[dict[str, Any]] = []
        rank_improved = 0
        rank_worsened = 0
        for s_id, asg_a in map_a.items():
            if s_id in map_b:
                asg_b = map_b[s_id]
                if asg_a.project_id != asg_b.project_id:
                    r_a = asg_a.preference_rank or 99
                    r_b = asg_b.preference_rank or 99
                    fit_a = (
                        asg_a.skill_fit_score
                        if asg_a.skill_fit_score is not None
                        else 0.5
                    )
                    fit_b = (
                        asg_b.skill_fit_score
                        if asg_b.skill_fit_score is not None
                        else 0.5
                    )
                    if r_b < r_a:
                        rank_change = "IMPROVED"
                        rank_improved += 1
                    elif r_b > r_a:
                        rank_change = "WORSENED"
                        rank_worsened += 1
                    else:
                        rank_change = "SAME"

                    changed.append(
                        {
                            "student_id": s_id,
                            "student_name": s_id,
                            "project_a": asg_a.project_id,
                            "project_a_id": asg_a.project_id,
                            "project_a_title": asg_a.project_id,
                            "rank_a": asg_a.preference_rank,
                            "skill_fit_a": fit_a,
                            "project_b": asg_b.project_id,
                            "project_b_id": asg_b.project_id,
                            "project_b_title": asg_b.project_id,
                            "rank_b": asg_b.preference_rank,
                            "skill_fit_b": fit_b,
                            "rank_delta": r_b - r_a,
                            "rank_change": rank_change,
                        }
                    )

        ind_a = sol_a.indicators
        ind_b = sol_b.indicators

        eff_a = ind_a.get("efficiency", {})
        eff_b = ind_b.get("efficiency", {})
        fair_a = ind_a.get("fairness", {})
        fair_b = ind_b.get("fairness", {})

        delta_metrics: dict[str, Any] = {
            "mean_skill_fit_delta": round(
                eff_b.get("mean_skill_fit", 0.0)
                - eff_a.get("mean_skill_fit", 0.0),
                4,
            ),
            "mean_rank_delta": round(
                fair_b.get("mean_rank", 0.0) - fair_a.get("mean_rank", 0.0),
                2,
            ),
            "gini_delta": round(
                fair_b.get("rank_gini", 0.0) - fair_a.get("rank_gini", 0.0),
                4,
            ),
        }

        return models.RunComparison(
            solution_a_id=solution_a_id,
            solution_a_alt=sol_a.alternative_number,
            solution_b_id=solution_b_id,
            solution_b_alt=sol_b.alternative_number,
            changed_assignments=changed,
            changed_students_count=len(changed),
            total_students=len(sol_a.assignments),
            is_distinct=len(changed) > 0,
            rank_improved_count=rank_improved,
            rank_worsened_count=rank_worsened,
            delta_metrics=delta_metrics,
            delta_mean_skill_fit=delta_metrics.get(
                "mean_skill_fit_delta", 0.0
            ),
            delta_mean_rank=delta_metrics.get("mean_rank_delta", 0.0),
            trade_off_summary=[
                f"{len(changed)} student(s) reallocated across alternatives."
            ],
        )
