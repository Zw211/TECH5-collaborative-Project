"""Calculators for feasibility, efficiency, fairness, and trade-offs.

This module provides analytical functions to evaluate solutions according to
the requirements in Section 7 of the TECH5 specification.

Students (Team B) must implement these analytical functions to compute
student-project skill fit, Gini inequality, solution indicators, and
side-by-side trade-off comparisons.
"""

import math
from typing import Any

from app.domain import models


def calculate_assignment_skill_fit(
    student: models.Student,
    project: models.Project,
) -> tuple[float, list[str]]:
    """Calculate skill fit and unmet skills for a student-project pair.

    In compliance with Section 7.2 of the TECH5 specification, skill fit
    evaluates how well the candidate student satisfies the required technical
    skills of the target project.

    Mandatory and optional requirements have equal weight in this score.
    Input levels must have passed domain validation. Missing skills count as
    zero; exceeding a requirement gives no extra credit. This individual score
    does not decide mandatory team coverage.

    Args:
        student: The student under evaluation.
        project: The project under evaluation.

    Returns:
        A tuple of (skill_fit_score [0.0, 1.0], list_of_unmet_skill_ids).
        Projects with no requirements have score 1.0 and no unmet skills.
    """
    if not project.requirements:
        return 1.0, []

    scores = []
    unmet = []
    for requirement in project.requirements:
        level = student.get_skill_level(requirement.skill_id)
        scores.append(min(level / requirement.minimum_level, 1.0))
        if level < requirement.minimum_level:
            unmet.append(requirement.skill_id)
    return sum(scores) / len(scores), unmet


def calculate_gini(values: list[float]) -> float:
    """Calculates the Gini coefficient of inequality for non-negative values.

    In compliance with Section 7.3 of the TECH5 specification, the Gini
    coefficient measures the inequality/fairness in student preference rank
    distribution (0.0 represents perfect equality, 1.0 represents extreme
    inequality).

    Args:
        values: Non-negative numerical series (e.g. assigned preference ranks).

    Returns:
        The Gini coefficient in [0.0, 1.0].

    Empty input and all-zero values return 0. The calculation sorts the
    values and uses G = sum((2*i-n-1)*x[i]) / (n*sum(x)), with i starting at 1.
    Scaling by the maximum prevents overflow without changing inequality.

    Raises:
        ValueError: A value is negative or nonfinite.
    """
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("Gini values must be finite and non-negative.")
    if not values or max(values) == 0:
        return 0.0
    maximum = max(values)
    ordered = sorted(value / maximum for value in values)
    count = len(ordered)
    weighted_sum = sum(
        (2 * index - count - 1) * value
        for index, value in enumerate(ordered, start=1)
    )
    return weighted_sum / (count * sum(ordered))


def compute_solution_indicators(
    students: list[models.Student],
    projects: list[models.Project],
    assignments: list[models.Assignment],
    fixed_assignments: list[models.FixedAssignment] | None = None,
) -> dict[str, Any]:
    """Computes comprehensive feasibility, efficiency, and fairness indicators.

    Evaluates a solution across the four dimensions defined in the
    specification:
    1. Feasibility: Exact student count, capacity bounds, fixed assignments.
    2. Efficiency: Mean skill-fit score, unmet soft requirements count.
    3. Fairness: Rank distribution, mean rank, worst rank, unranked count, Gini.
    4. Capacity: Total assigned, total capacity, overall utilization,
        per-project.

    Args:
        students: Complete cohort of students.
        projects: Catalog of semester projects.
        assignments: List of student-to-project allocations.
        fixed_assignments: Optional list of locked pre-allocations.

    Returns:
        A mapping with feasibility, efficiency, fairness, and capacity
        sections. These report violations, mean skill fit, preference ranks,
        rank Gini, overall utilization, and per-project capacity figures.

    Assignment rank/fit metadata is aggregated as supplied. Cohort inputs must
    already be validated. Invalid allocation rows are reported as violations;
    summaries exclude unknown IDs and repeated student rows.
    """
    student_by_id = {student.id: student for student in students}
    project_by_id = {project.id: project for project in projects}
    teams: dict[str, list[models.Student]] = {p.id: [] for p in projects}
    accepted: list[models.Assignment] = []
    assigned: dict[str, str] = {}
    violations = []
    if not students or not projects:
        violations.append("A nonempty cohort and project catalog are required.")
    for assignment in assignments:
        sid, pid = assignment.student_id, assignment.project_id
        if sid not in student_by_id or pid not in project_by_id:
            violations.append(
                f"Unknown student/project in assignment {sid}/{pid}."
            )
            continue
        if sid in assigned:
            violations.append(f"Student {sid} is assigned more than once.")
            continue
        assigned[sid] = pid
        teams[pid].append(student_by_id[sid])
        accepted.append(assignment)
    for sid in student_by_id:
        if sid not in assigned:
            violations.append(f"Student {sid} has no assignment.")
    for project in projects:
        team = teams[project.id]
        if not project.min_capacity <= len(team) <= project.max_capacity:
            violations.append(f"Capacity violation for project {project.id}.")
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
                violations.append(
                    f"Project {project.id} lacks mandatory skill "
                    f"{requirement.skill_id}."
                )
    for lock in fixed_assignments or []:
        if assigned.get(lock.student_id) != lock.project_id:
            violations.append(
                f"Fixed assignment changed for {lock.student_id}."
            )

    individual_gaps = sum(
        1
        for assignment in accepted
        for requirement in project_by_id[assignment.project_id].requirements
        if not requirement.is_mandatory
        and student_by_id[assignment.student_id].get_skill_level(
            requirement.skill_id
        )
        < requirement.minimum_level
    )
    count = len(accepted)
    total_fit = sum(a.skill_fit_score for a in accepted)
    max_preferences = max((len(s.preferences) for s in students), default=0)
    fairness = _rank_indicators(accepted, max_preferences)
    total_capacity = sum(p.max_capacity for p in projects)
    return {
        "feasibility": {
            "is_feasible": not violations,
            "violations": violations,
            "assigned_count": count,
            "total_students": len(students),
        },
        "efficiency": {
            "mean_skill_fit": total_fit / count if count else 0.0,
            "total_skill_fit_sum": total_fit,
            "individual_unmet_soft_requirements_count": individual_gaps,
            # Compatibility alias for existing templates/recommendations.
            "unmet_soft_requirements_count": individual_gaps,
            "soft_requirement_count_scope": (
                "individual_student_project_requirement"
            ),
        },
        "fairness": fairness,
        "capacity": {
            "total_assigned": count,
            "total_capacity": total_capacity,
            "overall_utilization_pct": (
                100 * count / total_capacity if total_capacity else 0.0
            ),
            "projects": {
                p.id: {
                    "assigned_count": len(teams[p.id]),
                    "min_capacity": p.min_capacity,
                    "max_capacity": p.max_capacity,
                    "utilization_pct": (
                        100 * len(teams[p.id]) / p.max_capacity
                        if p.max_capacity
                        else 0.0
                    ),
                }
                for p in projects
            },
        },
    }


def _rank_indicators(
    assignments: list[models.Assignment],
    max_preferences: int,
) -> dict[str, Any]:
    """Use cohort M+1 for numerical statistics, not actual rank labels."""
    penalty = max_preferences + 1
    ranks = [a.preference_rank for a in assignments]
    values = [rank if rank is not None else penalty for rank in ranks]
    count = len(values)
    mean = sum(values) / count if count else 0.0
    unranked = ranks.count(None)
    return {
        "max_preferences": max_preferences,
        "unranked_penalty": penalty,
        "rank_statistics_scope": "actual_ranks_with_M_plus_1_unranked_penalty",
        "rank_distribution": {
            f"rank_{rank}": ranks.count(rank)
            for rank in sorted({r for r in ranks if r is not None})
        },
        "unranked_count": unranked,
        "unranked_pct": 100 * unranked / count if count else 0.0,
        "mean_rank": mean,
        "worst_rank": max(values, default=0),
        "rank_variance": (
            sum((value - mean) ** 2 for value in values) / count
            if count
            else 0.0
        ),
        "rank_gini": calculate_gini(values),
    }


def compare_two_solutions(
    solution_a: models.Solution,
    solution_b: models.Solution,
) -> dict[str, Any]:
    """Performs detailed trade-off comparison between two alternative solutions.

    In compliance with Section 7.4 of the specification, identifies:
    - Changed student allocations between solutions A and B.
    - Improved and worsened student preference ranks.
    - Deltas in mean skill-fit, mean rank, and Gini coefficient.
    - Human-readable trade-off summary statements.

    Args:
        solution_a: Baseline solution.
        solution_b: Alternative solution to compare against A.

    Returns:
        Dictionary documenting differences, changed assignments, and trade-offs:
        {
            "solution_a_id": str,
            "solution_b_id": str,
            "is_distinct": bool,
            "changed_students_count": int,
            "changed_assignments": list[dict[str, Any]],
            "delta_metrics": dict[str, Any],
            "trade_off_summary": list[str]
        }

    Raises:
        ValueError: Student sets, unique IDs, or recorded penalties conflict.
        KeyError: Required mean skill-fit or rank indicators are missing.
    """
    map_a = {a.student_id: a for a in solution_a.assignments}
    map_b = {a.student_id: a for a in solution_b.assignments}
    if (
        len(map_a) != len(solution_a.assignments)
        or len(map_b) != len(solution_b.assignments)
        or set(map_a) != set(map_b)
    ):
        raise ValueError(
            "Comparisons require the same uniquely assigned students."
        )
    fair_a = solution_a.indicators.get("fairness", {})
    fair_b = solution_b.indicators.get("fairness", {})
    penalty_a = fair_a.get("unranked_penalty")
    penalty_b = fair_b.get("unranked_penalty")
    if (
        penalty_a is not None
        and penalty_b is not None
        and penalty_a != penalty_b
    ):
        raise ValueError("Rank comparisons require the same cohort penalty.")
    penalty = penalty_a if penalty_a == penalty_b else None
    changed = []
    improved = worsened = 0
    for sid in sorted(map_a):
        a, b = map_a[sid], map_b[sid]
        if a.project_id == b.project_id:
            continue
        rank_a, rank_b = a.preference_rank, b.preference_rank
        if rank_a == rank_b:
            direction = "SAME"
        elif rank_b is None or (rank_a is not None and rank_b > rank_a):
            direction = "WORSENED"
            worsened += 1
        else:
            direction = "IMPROVED"
            improved += 1
        numerical_a = rank_a if rank_a is not None else penalty
        numerical_b = rank_b if rank_b is not None else penalty
        changed.append(
            {
                "student_id": sid,
                "project_a": a.project_id,
                "project_a_id": a.project_id,
                "project_b": b.project_id,
                "project_b_id": b.project_id,
                "rank_a": rank_a,
                "rank_b": rank_b,
                "skill_fit_a": a.skill_fit_score,
                "skill_fit_b": b.skill_fit_score,
                "rank_change": direction,
                "rank_delta": (
                    numerical_b - numerical_a
                    if numerical_a is not None and numerical_b is not None
                    else None
                ),
            }
        )
    eff_a = solution_a.indicators.get("efficiency", {})
    eff_b = solution_b.indicators.get("efficiency", {})
    # Core indicators are required; missing data must not become fake zeros.
    fit_delta = round(eff_b["mean_skill_fit"] - eff_a["mean_skill_fit"], 10)
    rank_delta = round(fair_b["mean_rank"] - fair_a["mean_rank"], 10)
    unranked_delta = fair_b["unranked_count"] - fair_a["unranked_count"]
    deltas = {"mean_skill_fit_delta": fit_delta, "mean_rank_delta": rank_delta}
    if "rank_gini" in fair_a and "rank_gini" in fair_b:
        deltas["gini_delta"] = round(
            fair_b["rank_gini"] - fair_a["rank_gini"], 10
        )
    summary = [
        f"{len(changed)} student(s) changed project; {improved} improved and "
        f"{worsened} worsened their preference outcome.",
        f"B minus A: mean skill fit {fit_delta:+g}, mean rank {rank_delta:+g}, "
        f"unranked count {unranked_delta:+d}.",
    ]
    if penalty is None:
        summary.append(
            "No common unranked penalty recorded; unranked rank "
            "deltas are unavailable. Aggregate deltas use stored metrics."
        )
    return models.RunComparison(
        solution_a_id=solution_a.id,
        solution_b_id=solution_b.id,
        solution_a_alt=solution_a.alternative_number,
        solution_b_alt=solution_b.alternative_number,
        delta_metrics=deltas,
        changed_assignments=changed,
        changed_students_count=len(changed),
        total_students=len(map_a),
        is_distinct=bool(changed),
        rank_improved_count=improved,
        rank_worsened_count=worsened,
        delta_mean_skill_fit=fit_delta,
        delta_mean_rank=rank_delta,
        delta_unranked_count=unranked_delta,
        trade_off_summary=summary,
    ).to_dict()
