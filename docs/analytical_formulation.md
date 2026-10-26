# Analytical Requirements & Mathematical Modeling Guide
## TECH5 Collaborative Project — Assignment Engine Guidance

> [!IMPORTANT]
> **Starter Carcass Notice:**  
> This document outlines the analytical requirements for the Student-to-Project Assignment System. Student teams must formulate their own mathematical model, implement it in `app/engine/solvers.py` and `app/engine/metrics.py`, and complete their formal submission using the template provided in [`docs/analytical_note_template.md`](analytical_note_template.md).

---

## 1. Problem Overview & Scope

The decision support system assigns a cohort of students $S$ to a set of semester projects $P$, taking into account:
1. **Student Ranked Preferences**: Students rank projects from most to least preferred.
2. **Skill Proficiencies & Project Requirements**: Students have proficiencies across catalogued skills $K$; projects declare minimum required proficiency levels (some of which may be designated as mandatory).
3. **Project Capacities**: Each project $p$ has a minimum headcount $l_p$ and maximum headcount $u_p$.
4. **Administrative Fixed Assignments**: Pre-allocated student-to-project locks $(s, p) \in F$ specified by coordinators must be strictly enforced.

The Assignment Engine team (Team B) is responsible for proposing an assignment methodology suitable for this problem and approved by the course responsible (e.g., Integer Linear Programming via PuLP/CBC, heuristic search, or stable matching).

---

## 2. Key Modeling Challenges for Team B

### 2.1 Multi-Objective Optimization
Academic project assignment inherently features competing objectives:
- **Student Satisfaction**: Maximizing assigned preference ranks (or minimizing regret).
- **Skill Alignment**: Maximizing technical suitability and project delivery feasibility.
- **Fairness & Equity**: Minimizing inequality in student outcomes, avoiding students assigned to undesirable projects, and controlling worst-case regret.

Team B must implement at least two distinct optimization strategies (plus a balanced compromise) conforming to the `AssignmentStrategy` abstract base class in `app/engine/solvers.py`:
- `preference`: Prioritize student satisfaction.
- `skill`: Prioritize technical competence alignment.
- `balanced`: Trade off preference satisfaction against skill coverage.

### 2.2 Pareto Alternatives & No-Good Integer Cuts
Decision-makers require genuinely different solutions to compare:
- An alternative is distinct if and only if **at least one student receives a different project allocation**.
- If using an ILP solver, distinct alternatives can be discovered sequentially by adding **no-good integer cuts** after each solution is found.
- If no additional feasible solutions exist, the engine must accurately report this condition rather than fabricating duplicate solutions.

### 2.3 Hard vs. Soft Constraints
- **Hard Constraints**: Must never be violated in any feasible solution:
  - Exact allocation: Every student gets exactly one project.
  - Headcount limits: $l_p \le \text{headcount}_p \le u_p$.
  - Fixed locks: Pre-allocated students remain locked to their assigned project.
  - Mandatory skills: Mandatory qualifications must be satisfied by assigned students.
- **Soft Requirements**: Non-mandatory project skill requirements should be optimized where possible, with unmet soft requirements recorded in solution diagnostics.

---

## 3. Required Analytical Indicators

Section 6 of `projectTech5.tex` specifies four categories of analytical indicators to implement in `app/engine/metrics.py`:

| Category | Required Measures |
|---|---|
| **Feasibility** | Allocation completeness, capacity limit compliance, fixed assignment preservation, mandatory skill coverage. |
| **Efficiency** | Mean skill-fit score $\bar{\sigma} \in [0, 1]$, mean preference rank $\bar{r}$. |
| **Fairness** | Distribution of assigned preference ranks, count of unranked allocations, worst assigned rank ($r_{\max}$), and **one student-proposed fairness metric** (e.g., Gini coefficient $G$ or rank variance). |
| **Capacity** | Per-project capacity utilization $\text{Util}_p$, aggregate cohort capacity utilization. |

---

## 4. Deliverable 6 Requirements

Student teams must submit their formal **Analytical Note** as Deliverable 6.  
Use the provided template: **[`docs/analytical_note_template.md`](analytical_note_template.md)**.

The report will be assessed on:
- Formal, unambiguous mathematical notation (sets, indices, parameters, decision variables, constraints, objective functions).
- Mathematical definition of all indicators (feasibility, efficiency, fairness, capacity).
- Inspectable recommendation rules that clearly distinguish calculated evidence from advice.
- Documented assumptions, boundary conditions, and critical discussion of analytical limitations.


## Team B implementation baseline — Milestone 2 (2026-10-22)

The feature-branch solver now maximizes total assignment utility under the
confirmed exact-allocation, capacity, team-skill, and lock constraints.
Preference utility is `(M-r+1)/M` for ranked projects, with the same longest-list
length M across the cohort; unranked choices (and M=0) score zero. Skill utility
is the mean capped proficiency ratio over equally weighted requirements, or 1
when the project has no requirements. PREFERENCE uses weights (1,0), SKILL_FIT
uses (0,1), and BALANCED uses (0.5,0.5).

See [solver_spec.md](solver_spec.md) for complete definitions, interpretation,
and limitations, and [the living plan](solver_implementation_plan.md) for test
evidence. This implements individual fit, not fairness optimization or Pareto
search. Hard mandatory coverage is verified at team level independently of scores.
Instructor approval is still pending; application integration is not complete.
