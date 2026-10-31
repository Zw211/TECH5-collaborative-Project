# Deliverable 4: System Architecture Specification & Design Rationale

## 1. Executive Architectural Overview

The **TECH5 Student-to-Project Assignment Decision Support System (DSS)** is an integrated application engineered for the Norwegian School of Economics (NHH). It solves the complex combinatorial allocation problem of assigning a cohort of students to semester research and consulting projects based on multidimensional criteria: **student ranked preferences**, **student skill proficiencies**, **project skill requirements**, **project capacity bounds**, and **administrative pre-allocation locks**.

In accordance with the updated project specification (Sections 5, 7, 8, and 15), the system is architected as **two decoupled, modular application components** running within a single integrated Python application:

1. **Component A (Visualization & Recommendation Component)**:
   - Manages user workflow, cohort data inspection, CRUD interfaces, benchmark scenario seeding, role switching (Admin, Coordinator, Student Viewer), multi-solution visual side-by-side trade-off comparisons, and evidence-backed recommendations.
2. **Component B (Assignment Engine)**:
   - Validates input feasibility, executes mathematical Integer Linear Programming (PuLP) using the **Strategy Pattern** (`PreferenceOrientedSolver`, `SkillFitOrientedSolver`, `BalancedTradeoffSolver`), generates distinct feasible alternatives by repeatedly solving the selected objective with integer no-good cuts, evaluates multidimensional quality/fairness metrics, and captures diagnostics.

Assignment execution and comparison use an **internal Python component contract** (`app/contract/contract.py`), backed by a shared relational SQLite 3NF persistence layer (`app/persistence`). Routes also call the recommendation functions directly and use repositories to retrieve saved data.

---

## 2. Component Diagram & Internal Interface

```mermaid
flowchart TD
    subgraph Component_A["Component A: Visualization & Recommendation (app/visualization)"]
        UI[Jinja2 HTML5 / CSS3 Responsive UI]
        WebRoutes[Flask Web Blueprint: visualization_web]
        RoleAuth[Role-Based Access Control: Admin / Coord / Student]
        RecPresenter[Recommendation & Trade-Off Presentation]
    end

    subgraph InternalContract["Internal Component Contract (app/contract/contract.py)"]
        ContractABC["AssignmentEngineContract (ABC)"]
        DTOs["RunRequest | ValidationOutcome | DiagnosticInfo | RunComparison"]
    end

    subgraph Component_B["Component B: Assignment Engine (app/engine)"]
        SolverEngine["AssignmentEngine (implements Contract)"]
        StrategyPattern["Strategy Pattern: Preference, Skill-Fit, Balanced"]
        PuLPSolver["PuLP ILP Solver & No-Good Cuts"]
        MetricsEngine["Analytical Indicators & Gini Fairness Engine"]
        Recommendations["Recommendation Functions (app/engine/recommendations.py)"]
    end

    DomainModels["Domain Dataclasses (app/domain/models.py)"]
    ValidationEngine["Domain Feasibility Validator (app/domain/validation.py)"]

    subgraph Persistence["Shared Relational Persistence (app/persistence)"]
        DBMgr["DatabaseManager (SQLite WAL Mode, Foreign Keys)"]
        Repos["Repositories: Cohort, Students, Projects, Skills, Locks, Runs"]
        Schema["3NF Relational Schema & Performance Indexes"]
    end

    UI --> WebRoutes
    WebRoutes --> RoleAuth
    WebRoutes --> RecPresenter
    WebRoutes --> Recommendations
    Recommendations -->|Reads stored solution indicators| DomainModels
    WebRoutes --> ValidationEngine
    SolverEngine --> DomainModels
    WebRoutes -->|Invokes Python Methods| ContractABC
    ContractABC -.->|Implemented By| SolverEngine

    SolverEngine --> StrategyPattern
    StrategyPattern --> PuLPSolver
    SolverEngine --> MetricsEngine
    MetricsEngine --> DomainModels
    SolverEngine --> ValidationEngine

    WebRoutes --> Repos
    SolverEngine --> Repos
    Repos --> DBMgr
    DBMgr --> Schema
```

---

## 3. Design Rationale: Two-Component Modular Monolith vs. Microservices

### 3.1 Motivation for In-Process Two-Component Architecture
1. **Curricular Alignment & Feasibility**:
   - The primary pedagogical objective is object-oriented software design, relational database integration, and decision support. Microservices introduce substantial operational complexity (distributed networking, ports, HTTP status translation, retries, serialization boilerplate) that distracts from the core analytical problem.
2. **High Modularity Without Operational Overhead**:
   - Component A and Component B maintain strict separation of concerns. Component B has zero knowledge of Flask request objects, HTML templates, or cookies. It can be instantiated, validated, and tested headlessly in pure Python scripts or test harnesses.
3. **Type Safety & Compiler Diagnostics**:
   - In-process contract calls pass typed dataclasses (`RunRequest`, `ValidationOutcome`, `RunComparison`) directly. Type checkers (`mypy`, `pylint`) and IDEs provide immediate syntax and type validation, eliminating runtime JSON schema mismatch errors.
4. **Performance & Determinism**:
   - Direct method invocations eliminate JSON serialization/deserialization CPU cycles and network socket latency, allowing instant interactive comparison and optimization execution.

---

## 4. Object-Oriented Architecture & Design Patterns

### 4.1 Strategy Pattern (Assignment Algorithms)
The Assignment Engine defines an abstract base strategy `AssignmentStrategy(abc.ABC)` with concrete subclasses:
- `PreferenceOrientedSolver`: Maximizes student ranked preferences (assigning rank 1 awards highest utility, penalizing unranked assignments).
- `SkillFitOrientedSolver`: Maximizes qualification fit across all required project skills.
- `BalancedTradeoffSolver`: Combines normalized preference utility and individual skill fit with equal weights.

```mermaid
classDiagram
    AssignmentStrategy <|-- PreferenceOrientedSolver
    AssignmentStrategy <|-- SkillFitOrientedSolver
    AssignmentStrategy <|-- BalancedTradeoffSolver
    class AssignmentStrategy {
        <<abstract>>
        +calculate_cost_or_utility()
        +solve()
    }
```

Each no-good cut excludes one complete prior student-to-project allocation.
The engine repeats the selected strategy until the requested limit, exhaustion,
or an unsuccessful solve; returned alternatives are distinct, without a
Pareto-optimality guarantee.

### 4.2 Abstract Contract Pattern (Component Boundary)
`AssignmentEngineContract` defines the public interface required by Component A. Concrete `AssignmentEngine` implements all contract methods, ensuring that any mock or alternative solver can be substituted without touching Component A.

### 4.3 Repository Pattern (Data Access Layer)
Persistence operations are encapsulated into domain repositories:
- `CohortRepository`: Replaces students, projects, skills, and locks atomically.
- `StudentRepository`: Manages `students`, `student_skills`, and `preferences`.
- `ProjectRepository`: Manages `projects` and `project_requirements`.
- `SkillRepository`: Manages defined competencies.
- `FixedAssignmentRepository`: Manages administrative pre-allocation locks.
- `RunRepository`: Manages `assignment_runs`, `solutions`, and `assignments`.

### 4.4 Main Class Relationships

These four class views follow `app/domain/models.py`, `app/contract/contract.py`,
`app/engine/solvers.py`, and `app/persistence/`. Solid associations show retained
objects; dashed arrows show calls or types used in inputs/outputs. Associations
labelled with IDs are logical references, not Python object fields.
`Student.skills` stores skill IDs mapped to levels; `StudentSkill` is the
corresponding value-object type, not a list held by `Student`. Collection
multiplicities allow empty inputs and unsuccessful runs; a feasible solution
assigns every student exactly once.

```mermaid
classDiagram
    AssignmentEngineContract <|-- AssignmentEngine
    AssignmentEngineContract <|-- MockAssignmentEngine
    class AssignmentEngineContract {
        <<abstract>>
        +validate_inputs()
        +execute_run()
        +list_runs()
        +get_run()
        +get_solution()
        +compare_solutions()
    }
    AssignmentEngineContract ..> RunRequest : accepts
    AssignmentEngineContract ..> ValidationOutcome : returns
    AssignmentEngineContract ..> AssignmentRun : returns
    AssignmentEngineContract ..> Solution : returns
    AssignmentEngineContract ..> RunComparison : returns
    AssignmentEngine "1" --> "3" AssignmentStrategy : strategies
    AssignmentStrategy <|-- PreferenceOrientedSolver
    AssignmentStrategy <|-- SkillFitOrientedSolver
    AssignmentStrategy <|-- BalancedTradeoffSolver
    AssignmentStrategy ..> DiagnosticInfo : serializes diagnostics
    AssignmentEngine "0..*" --> "1" RunRepository : run_repo
    AssignmentEngine ..> SkillRepository : saves cohort
    AssignmentEngine ..> ProjectRepository : saves cohort
    AssignmentEngine ..> StudentRepository : saves cohort
    AssignmentEngine ..> FixedAssignmentRepository : saves locks
```

Domain collections and ID references:

```mermaid
---
config:
  nodeSpacing: 90
  rankSpacing: 180
---
classDiagram
    direction LR
    RunRequest "1" --> "0..*" Student : students
    RunRequest "1" --> "0..*" Project : projects
    RunRequest "1" --> "0..*" Skill : optional skills
    RunRequest "1" --> "0..*" FixedAssignment : optional locks
    Student "1" --> "0..*" Preference : preferences
    Project "1" --> "0..*" ProjectRequirement : requirements
    Student "1" -- "0..*" StudentSkill
    Skill "1" -- "0..*" StudentSkill : skill_id
    Project "1" -- "0..*" Preference : project_id
    Skill "1" -- "0..*" ProjectRequirement : skill_id
    Student "1" -- "0..1" FixedAssignment : student_id
    Project "1" -- "0..*" FixedAssignment : project_id
```

Run results and allocation references:

```mermaid
classDiagram
    direction LR
    AssignmentRun "1" --> "0..*" Solution : solutions
    Solution "1" --> "0..*" Assignment : assignments
    Student "1" -- "0..*" Assignment : student_id
    Project "1" -- "0..*" Assignment : project_id
    RunComparison ..> Solution : solution_a_id and solution_b_id
```

Persistence collaborators and mapped domain types:

```mermaid
---
config:
  nodeSpacing: 90
  rankSpacing: 180
---
classDiagram
    direction LR
    CohortRepository "0..*" --> "1" DatabaseManager : db
    SkillRepository "0..*" --> "1" DatabaseManager : db
    StudentRepository "0..*" --> "1" DatabaseManager : db
    ProjectRepository "0..*" --> "1" DatabaseManager : db
    FixedAssignmentRepository "0..*" --> "1" DatabaseManager : db
    RunRepository "0..*" --> "1" DatabaseManager : db
    CohortRepository ..> Student : replaces cohort
    CohortRepository ..> Project : replaces cohort
    CohortRepository ..> Skill : replaces cohort
    CohortRepository ..> FixedAssignment : replaces locks
    SkillRepository ..> Skill : maps
    StudentRepository ..> Student : maps
    ProjectRepository ..> Project : maps
    FixedAssignmentRepository ..> FixedAssignment : maps
    RunRepository ..> AssignmentRun : saves and loads
    RunRepository ..> Solution : loads
    DatabaseManager ..> InvalidDatabaseRecords : raises
```

The repositories share a `DatabaseManager`; its `transaction()` context can
supply a transaction-bound manager so cohort and run writes commit together.
Domain IDs and the database constraints below define saved-record references.

---

## 5. Relational Database Architecture

This diagram follows `app/persistence/schema.sql`. Every foreign key uses
`ON DELETE CASCADE`. Composite unique constraints also prevent duplicate
preference ranks within a student, duplicate alternative numbers within a run, and duplicate students
within a solution.

```mermaid
erDiagram
    students ||--o{ student_skills : "possesses"
    skills ||--o{ student_skills : "classified under"
    students ||--o{ preferences : "submits"
    projects ||--o{ preferences : "ranked in"
    projects ||--o{ project_requirements : "demands"
    skills ||--o{ project_requirements : "specified by"
    students ||--o| fixed_assignments : "locked to"
    projects ||--o{ fixed_assignments : "hosts"
    assignment_runs ||--o{ solutions : "produces"
    solutions ||--o{ assignments : "allocates"
    students ||--o{ assignments : "assigned"
    projects ||--o{ assignments : "contains"

    students {
        TEXT id PK
        TEXT display_name
    }
    projects {
        TEXT id PK
        TEXT title
        TEXT description
        INTEGER min_capacity
        INTEGER max_capacity
    }
    skills {
        TEXT id PK
        TEXT name UK
        TEXT description
    }
    student_skills {
        TEXT student_id PK,FK
        TEXT skill_id PK,FK
        INTEGER level
    }
    project_requirements {
        TEXT project_id PK,FK
        TEXT skill_id PK,FK
        INTEGER minimum_level
        INTEGER is_mandatory
    }
    preferences {
        TEXT student_id PK,FK
        TEXT project_id PK,FK
        INTEGER rank
    }
    fixed_assignments {
        INTEGER id PK
        TEXT student_id FK,UK
        TEXT project_id FK
        TEXT status
        TEXT reason
    }
    assignment_runs {
        TEXT id PK
        TEXT created_at
        TEXT status
        TEXT configuration
        TEXT diagnostics
    }
    solutions {
        TEXT id PK
        TEXT run_id FK
        INTEGER alternative_number
        TEXT strategy_name
        REAL objective_value
        TEXT indicators
        TEXT warnings
        TEXT diagnostics
    }
    assignments {
        INTEGER id PK
        TEXT solution_id FK
        TEXT student_id FK
        TEXT project_id FK
        INTEGER is_fixed
        INTEGER preference_rank
        REAL skill_fit_score
        TEXT unmet_requirements
    }
```

---

## 6. Role-Based Access Control (RBAC)

The application models three explicit business roles in `app/visualization/auth.py`:
1. **Course Administrator (`ADMIN`)**: Full authorization. Can edit students, projects, skills, and fixed assignments, trigger optimization runs, and switch active roles.
2. **Program Coordinator (`COORDINATOR`)**: Operational authorization. Can manage fixed assignment locks, trigger solver runs, and inspect detailed recommendations and comparisons. Read-only on baseline student data.
3. **Student Viewer (`STUDENT`)**: Transparency view. Can browse anonymized dashboard metrics, project descriptions, and high-level allocation summaries. Mutating actions are disabled.
