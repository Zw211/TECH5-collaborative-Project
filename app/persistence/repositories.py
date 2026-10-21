"""Repository pattern implementations for relational persistence.

This module encapsulates all SQL queries, transactions, and entity mapping
between database tables and domain models.
"""

import json

from app.domain import models
from app.persistence import database


class CohortRepository:
    """Replace related cohort records atomically after validation."""

    def __init__(self, db: database.DatabaseManager | None = None) -> None:
        """Initialize the repository with its database manager.

        Args:
            db: Shared database manager, or the application's default manager.
        """
        self.db = db or database.db_manager

    def replace(
        self,
        students: list[models.Student],
        projects: list[models.Project],
        skills: list[models.Skill],
        fixed_assignments: list[models.FixedAssignment],
    ) -> None:
        """Replace the cohort, rolling back every change on failure.

        Args:
            students: Complete replacement student cohort.
            projects: Complete replacement project catalogue.
            skills: Complete replacement skill catalogue.
            fixed_assignments: Replacement administrative locks.

        Raises:
            sqlite3.DatabaseError: Replacement could not be saved atomically.
        """
        with self.db.connection() as conn:
            for statement in (
                "DELETE FROM fixed_assignments;",
                "DELETE FROM preferences;",
                "DELETE FROM student_skills;",
                "DELETE FROM project_requirements;",
                "DELETE FROM students;",
                "DELETE FROM projects;",
                "DELETE FROM skills;",
            ):
                conn.execute(statement)
            conn.executemany(
                "INSERT INTO skills (id, name, description) VALUES (?, ?, ?);",
                [(skill.id, skill.name, skill.description) for skill in skills],
            )
            for project in projects:
                conn.execute(
                    "INSERT INTO projects (id, title, description, "
                    "min_capacity, max_capacity) VALUES (?, ?, ?, ?, ?);",
                    (
                        project.id,
                        project.title,
                        project.description,
                        project.min_capacity,
                        project.max_capacity,
                    ),
                )
                for requirement in project.requirements:
                    conn.execute(
                        "INSERT INTO project_requirements (project_id, "
                        "skill_id, minimum_level, is_mandatory) VALUES (?, "
                        "?, ?, ?);",
                        (
                            project.id,
                            requirement.skill_id,
                            requirement.minimum_level,
                            int(requirement.is_mandatory),
                        ),
                    )
            for student in students:
                conn.execute(
                    "INSERT INTO students (id, display_name) VALUES (?, ?);",
                    (student.id, student.display_name),
                )
                for skill_id, level in student.skills.items():
                    conn.execute(
                        "INSERT INTO student_skills VALUES (?, ?, ?);",
                        (student.id, skill_id, level),
                    )
                for preference in student.preferences:
                    conn.execute(
                        "INSERT INTO preferences VALUES (?, ?, ?);",
                        (student.id, preference.project_id, preference.rank),
                    )
            for fixed in fixed_assignments:
                conn.execute(
                    "INSERT INTO fixed_assignments (student_id, "
                    "project_id, status, reason) VALUES (?, ?, ?, ?);",
                    (
                        fixed.student_id,
                        fixed.project_id,
                        fixed.status,
                        fixed.reason,
                    ),
                )


class SkillRepository:
    """Repository managing skill catalog records."""

    def __init__(self, db: database.DatabaseManager | None = None) -> None:
        """Initialize the repository with its database manager.

        Args:
            db: Shared database manager, or the application's default manager.
        """
        self.db = db or database.db_manager

    def list_all(self) -> list[models.Skill]:
        """Retrieves all skills ordered by name."""
        rows = self.db.execute_query(
            "SELECT id, name, description FROM skills ORDER BY name ASC;"
        )
        return [
            models.Skill(
                id=row["id"],
                name=row["name"],
                description=row["description"],
            )
            for row in rows
        ]

    def get_by_id(self, skill_id: str) -> models.Skill | None:
        """Retrieves a skill by identifier."""
        rows = self.db.execute_query(
            "SELECT id, name, description FROM skills WHERE id = ?;",
            (skill_id,),
        )
        if not rows:
            return None
        row = rows[0]
        return models.Skill(
            id=row["id"],
            name=row["name"],
            description=row["description"],
        )

    def save(self, skill: models.Skill) -> None:
        """Inserts or updates a skill record."""
        self.db.execute_statement(
            """
            INSERT INTO skills (id, name, description)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description;
            """,
            (skill.id, skill.name, skill.description),
        )

    def delete(self, skill_id: str) -> bool:
        """Deletes a skill by identifier."""
        count = self.db.execute_statement(
            "DELETE FROM skills WHERE id = ?;", (skill_id,)
        )
        return count > 0


class StudentRepository:
    """Repository managing student roster, skills, and preferences."""

    def __init__(self, db: database.DatabaseManager | None = None) -> None:
        """Initialize the repository with its database manager.

        Args:
            db: Shared database manager, or the application's default manager.
        """
        self.db = db or database.db_manager

    def list_all(self) -> list[models.Student]:
        """Retrieves all students with their skills and ranked preferences."""
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, display_name FROM students "
                "ORDER BY display_name ASC;"
            )
            stud_rows = cur.fetchall()

            students: list[models.Student] = []
            for s_row in stud_rows:
                s_id = s_row["id"]
                cur.execute(
                    "SELECT skill_id, level FROM student_skills "
                    "WHERE student_id = ?;",
                    (s_id,),
                )
                skills_dict = {
                    row["skill_id"]: row["level"] for row in cur.fetchall()
                }

                cur.execute(
                    "SELECT project_id, rank FROM preferences "
                    "WHERE student_id = ? ORDER BY rank ASC;",
                    (s_id,),
                )
                preferences = [
                    models.Preference(
                        student_id=s_id,
                        project_id=p_row["project_id"],
                        rank=p_row["rank"],
                    )
                    for p_row in cur.fetchall()
                ]

                students.append(
                    models.Student(
                        id=s_id,
                        display_name=s_row["display_name"],
                        skills=skills_dict,
                        preferences=preferences,
                    )
                )
            return students

    def get_by_id(self, student_id: str) -> models.Student | None:
        """Retrieves an individual student by ID."""
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, display_name FROM students WHERE id = ?;",
                (student_id,),
            )
            s_row = cur.fetchone()
            if not s_row:
                return None

            cur.execute(
                "SELECT skill_id, level FROM student_skills "
                "WHERE student_id = ?;",
                (student_id,),
            )
            skills_dict = {
                row["skill_id"]: row["level"] for row in cur.fetchall()
            }

            cur.execute(
                "SELECT project_id, rank FROM preferences WHERE student_id = ? "
                "ORDER BY rank ASC;",
                (student_id,),
            )
            preferences = [
                models.Preference(
                    student_id=student_id,
                    project_id=p_row["project_id"],
                    rank=p_row["rank"],
                )
                for p_row in cur.fetchall()
            ]

            return models.Student(
                id=s_row["id"],
                display_name=s_row["display_name"],
                skills=skills_dict,
                preferences=preferences,
            )

    def save(self, student: models.Student) -> None:
        """Persists a student and updates their skills and preferences.

        Args:
            student: Student domain entity to persist.

        Raises:
            sqlite3.IntegrityError: If a foreign key constraint fails (e.g.,
                referenced project or skill does not exist in the database).
        """
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO students (id, display_name)
                VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    display_name = excluded.display_name;
                """,
                (student.id, student.display_name),
            )

            # Sync skills
            cur.execute(
                "DELETE FROM student_skills WHERE student_id = ?;",
                (student.id,),
            )
            for skill_id, level in student.skills.items():
                cur.execute(
                    """
                    INSERT INTO student_skills (student_id, skill_id, level)
                    VALUES (?, ?, ?);
                    """,
                    (student.id, skill_id, level),
                )

            # Sync preferences
            cur.execute(
                "DELETE FROM preferences WHERE student_id = ?;",
                (student.id,),
            )
            for pref in student.preferences:
                cur.execute(
                    """
                    INSERT INTO preferences (student_id, project_id, rank)
                    VALUES (?, ?, ?);
                    """,
                    (student.id, pref.project_id, pref.rank),
                )

    def delete(self, student_id: str) -> bool:
        """Deletes a student record (cascading to skills, preferences)."""
        count = self.db.execute_statement(
            "DELETE FROM students WHERE id = ?;", (student_id,)
        )
        return count > 0


class ProjectRepository:
    """Repository managing semester projects and requirements."""

    def __init__(self, db: database.DatabaseManager | None = None) -> None:
        """Initialize the repository with its database manager.

        Args:
            db: Shared database manager, or the application's default manager.
        """
        self.db = db or database.db_manager

    def list_all(self) -> list[models.Project]:
        """Retrieves all projects with requirements."""
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, title, description, min_capacity, max_capacity
                FROM projects ORDER BY id ASC;
                """
            )
            proj_rows = cur.fetchall()

            projects: list[models.Project] = []
            for p_row in proj_rows:
                p_id = p_row["id"]
                cur.execute(
                    """
                    SELECT skill_id, minimum_level, is_mandatory
                    FROM project_requirements
                    WHERE project_id = ?;
                    """,
                    (p_id,),
                )
                reqs = [
                    models.ProjectRequirement(
                        project_id=p_id,
                        skill_id=r_row["skill_id"],
                        minimum_level=r_row["minimum_level"],
                        is_mandatory=database.read_boolean(
                            r_row["is_mandatory"],
                            f"Project '{p_id}', skill '{r_row['skill_id']}'",
                        ),
                    )
                    for r_row in cur.fetchall()
                ]

                projects.append(
                    models.Project(
                        id=p_id,
                        title=p_row["title"],
                        description=p_row["description"],
                        min_capacity=p_row["min_capacity"],
                        max_capacity=p_row["max_capacity"],
                        requirements=reqs,
                    )
                )
            return projects

    def get_by_id(self, project_id: str) -> models.Project | None:
        """Retrieves an individual project by ID."""
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, title, description, min_capacity, max_capacity
                FROM projects WHERE id = ?;
                """,
                (project_id,),
            )
            p_row = cur.fetchone()
            if not p_row:
                return None

            cur.execute(
                """
                SELECT skill_id, minimum_level, is_mandatory
                FROM project_requirements WHERE project_id = ?;
                """,
                (project_id,),
            )
            reqs = [
                models.ProjectRequirement(
                    project_id=project_id,
                    skill_id=r_row["skill_id"],
                    minimum_level=r_row["minimum_level"],
                    is_mandatory=database.read_boolean(
                        r_row["is_mandatory"],
                        f"Project '{project_id}', skill '{r_row['skill_id']}'",
                    ),
                )
                for r_row in cur.fetchall()
            ]

            return models.Project(
                id=p_row["id"],
                title=p_row["title"],
                description=p_row["description"],
                min_capacity=p_row["min_capacity"],
                max_capacity=p_row["max_capacity"],
                requirements=reqs,
            )

    def save(self, project: models.Project) -> None:
        """Persists a project and synchronizes requirements."""
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO projects (
                    id, title, description, min_capacity, max_capacity
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    min_capacity = excluded.min_capacity,
                    max_capacity = excluded.max_capacity;
                """,
                (
                    project.id,
                    project.title,
                    project.description,
                    project.min_capacity,
                    project.max_capacity,
                ),
            )

            cur.execute(
                "DELETE FROM project_requirements WHERE project_id = ?;",
                (project.id,),
            )
            for req in project.requirements:
                cur.execute(
                    """
                    INSERT INTO project_requirements (
                        project_id, skill_id, minimum_level, is_mandatory
                    )
                    VALUES (?, ?, ?, ?);
                    """,
                    (
                        project.id,
                        req.skill_id,
                        req.minimum_level,
                        1 if req.is_mandatory else 0,
                    ),
                )

    def delete(self, project_id: str) -> bool:
        """Deletes a project record (cascading to requirements)."""
        count = self.db.execute_statement(
            "DELETE FROM projects WHERE id = ?;", (project_id,)
        )
        return count > 0


class FixedAssignmentRepository:
    """Repository managing administrative locked pre-allocations."""

    def __init__(self, db: database.DatabaseManager | None = None) -> None:
        """Initialize the repository with its database manager.

        Args:
            db: Shared database manager, or the application's default manager.
        """
        self.db = db or database.db_manager

    def list_all(self) -> list[models.FixedAssignment]:
        """Retrieves all fixed assignment constraints."""
        rows = self.db.execute_query(
            """
            SELECT student_id, project_id, status, reason
            FROM fixed_assignments
            ORDER BY student_id ASC;
            """
        )
        return [
            models.FixedAssignment(
                student_id=r["student_id"],
                project_id=r["project_id"],
                status=r["status"],
                reason=r["reason"],
            )
            for r in rows
        ]

    def save(self, fixed: models.FixedAssignment) -> None:
        """Persists a fixed assignment constraint."""
        self.db.execute_statement(
            """
            INSERT INTO fixed_assignments (
                student_id, project_id, status, reason
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                project_id = excluded.project_id,
                status = excluded.status,
                reason = excluded.reason;
            """,
            (fixed.student_id, fixed.project_id, fixed.status, fixed.reason),
        )

    def delete(self, student_id: str) -> bool:
        """Removes a fixed assignment constraint."""
        count = self.db.execute_statement(
            "DELETE FROM fixed_assignments WHERE student_id = ?;",
            (student_id,),
        )
        return count > 0


class RunRepository:
    """Repository managing assignment runs, solutions, and assignments."""

    def __init__(self, db: database.DatabaseManager | None = None) -> None:
        """Initialize the repository with its database manager.

        Args:
            db: Shared database manager, or the application's default manager.
        """
        self.db = db or database.db_manager

    def save_run(self, run: models.AssignmentRun) -> None:
        """Persists a full assignment run with solutions and allocations."""
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO assignment_runs (
                    id, created_at, status, configuration, diagnostics
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    diagnostics = excluded.diagnostics;
                """,
                (
                    run.id,
                    run.created_at,
                    run.status,
                    json.dumps(run.configuration),
                    json.dumps(run.diagnostics),
                ),
            )

            for sol in run.solutions:
                cur.execute(
                    """
                    INSERT INTO solutions (
                        id, run_id, alternative_number, strategy_name,
                        objective_value, indicators, warnings, diagnostics
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        objective_value = excluded.objective_value,
                        indicators = excluded.indicators,
                        warnings = excluded.warnings,
                        diagnostics = excluded.diagnostics;
                    """,
                    (
                        sol.id,
                        run.id,
                        sol.alternative_number,
                        sol.strategy_name,
                        sol.objective_value,
                        json.dumps(sol.indicators),
                        json.dumps(sol.warnings),
                        json.dumps(sol.diagnostics),
                    ),
                )

                cur.execute(
                    "DELETE FROM assignments WHERE solution_id = ?;",
                    (sol.id,),
                )
                for asg in sol.assignments:
                    cur.execute(
                        """
                        INSERT INTO assignments (
                            solution_id, student_id, project_id, is_fixed,
                            preference_rank, skill_fit_score, unmet_requirements
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            sol.id,
                            asg.student_id,
                            asg.project_id,
                            1 if asg.is_fixed else 0,
                            asg.preference_rank,
                            asg.skill_fit_score,
                            json.dumps(asg.unmet_requirements),
                        ),
                    )

    def list_runs(self, limit: int = 25) -> list[models.AssignmentRun]:
        """Retrieves recent optimization runs."""
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, created_at, status, configuration, diagnostics
                FROM assignment_runs
                ORDER BY created_at DESC
                LIMIT ?;
                """,
                (limit,),
            )
            run_rows = cur.fetchall()
            runs: list[models.AssignmentRun] = []
            for r in run_rows:
                run_obj = models.AssignmentRun(
                    id=r["id"],
                    created_at=r["created_at"],
                    status=r["status"],
                    configuration=json.loads(r["configuration"]),
                    diagnostics=json.loads(r["diagnostics"]),
                )
                # Load solutions count / metadata
                cur.execute(
                    """
                    SELECT id, run_id, alternative_number, strategy_name,
                           objective_value, indicators, warnings, diagnostics
                    FROM solutions WHERE run_id = ?
                    ORDER BY alternative_number ASC;
                    """,
                    (run_obj.id,),
                )
                sol_rows = cur.fetchall()
                for s in sol_rows:
                    run_obj.solutions.append(
                        models.Solution(
                            id=s["id"],
                            run_id=s["run_id"],
                            alternative_number=s["alternative_number"],
                            strategy_name=s["strategy_name"],
                            objective_value=s["objective_value"],
                            indicators=json.loads(s["indicators"]),
                            warnings=json.loads(s["warnings"]),
                            diagnostics=json.loads(s["diagnostics"]),
                        )
                    )
                runs.append(run_obj)
            return runs

    def get_run(self, run_id: str) -> models.AssignmentRun | None:
        """Retrieves an assignment run by ID with full solution details."""
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, created_at, status, configuration, diagnostics
                FROM assignment_runs WHERE id = ?;
                """,
                (run_id,),
            )
            r = cur.fetchone()
            if not r:
                return None

            run_obj = models.AssignmentRun(
                id=r["id"],
                created_at=r["created_at"],
                status=r["status"],
                configuration=json.loads(r["configuration"]),
                diagnostics=json.loads(r["diagnostics"]),
            )

            cur.execute(
                """
                SELECT id, run_id, alternative_number, strategy_name,
                       objective_value, indicators, warnings, diagnostics
                FROM solutions WHERE run_id = ? ORDER BY alternative_number ASC;
                """,
                (run_id,),
            )
            sol_rows = cur.fetchall()

            for s in sol_rows:
                cur.execute(
                    """
                    SELECT student_id, project_id, is_fixed, preference_rank,
                           skill_fit_score, unmet_requirements
                    FROM assignments WHERE solution_id = ?
                    ORDER BY preference_rank IS NULL, preference_rank ASC;
                    """,
                    (s["id"],),
                )
                asg_rows = cur.fetchall()
                assignments = [
                    models.Assignment(
                        student_id=a["student_id"],
                        project_id=a["project_id"],
                        is_fixed=bool(a["is_fixed"]),
                        preference_rank=a["preference_rank"],
                        skill_fit_score=a["skill_fit_score"],
                        unmet_requirements=json.loads(a["unmet_requirements"]),
                    )
                    for a in asg_rows
                ]

                run_obj.solutions.append(
                    models.Solution(
                        id=s["id"],
                        run_id=s["run_id"],
                        alternative_number=s["alternative_number"],
                        strategy_name=s["strategy_name"],
                        objective_value=s["objective_value"],
                        assignments=assignments,
                        indicators=json.loads(s["indicators"]),
                        warnings=json.loads(s["warnings"]),
                        diagnostics=json.loads(s["diagnostics"]),
                    )
                )

            return run_obj

    def get_solution(self, solution_id: str) -> models.Solution | None:
        """Retrieves a single solution by ID with assignments."""
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, run_id, alternative_number, strategy_name,
                       objective_value, indicators, warnings, diagnostics
                FROM solutions WHERE id = ?;
                """,
                (solution_id,),
            )
            s = cur.fetchone()
            if not s:
                return None

            cur.execute(
                """
                SELECT student_id, project_id, is_fixed, preference_rank,
                       skill_fit_score, unmet_requirements
                FROM assignments WHERE solution_id = ?
                ORDER BY preference_rank IS NULL, preference_rank ASC;
                """,
                (solution_id,),
            )
            asg_rows = cur.fetchall()
            assignments = [
                models.Assignment(
                    student_id=a["student_id"],
                    project_id=a["project_id"],
                    is_fixed=bool(a["is_fixed"]),
                    preference_rank=a["preference_rank"],
                    skill_fit_score=a["skill_fit_score"],
                    unmet_requirements=json.loads(a["unmet_requirements"]),
                )
                for a in asg_rows
            ]

            return models.Solution(
                id=s["id"],
                run_id=s["run_id"],
                alternative_number=s["alternative_number"],
                strategy_name=s["strategy_name"],
                objective_value=s["objective_value"],
                assignments=assignments,
                indicators=json.loads(s["indicators"]),
                warnings=json.loads(s["warnings"]),
                diagnostics=json.loads(s["diagnostics"]),
            )

    def clear_all_cohort_data(self) -> None:
        """Wipes student, project, preference, and fixed assignment data."""
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM fixed_assignments;")
            cur.execute("DELETE FROM preferences;")
            cur.execute("DELETE FROM student_skills;")
            cur.execute("DELETE FROM project_requirements;")
            cur.execute("DELETE FROM students;")
            cur.execute("DELETE FROM projects;")
            cur.execute("DELETE FROM skills;")

    def clear_all_current_solutions(self) -> None:
        """Delete all solutions and their parent runs."""
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM solutions;")
            cur.execute("DELETE FROM assignment_runs;")
