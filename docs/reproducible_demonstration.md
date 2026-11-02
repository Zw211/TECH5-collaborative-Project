# Deliverable 8: Reproducible Application Demonstration

Use the existing Flask application to demonstrate alternatives and a visible
trade-off, recommendations, a fixed assignment and rerun, and infeasibility.
Allow approximately 5–10 minutes. Run comparisons before changing scenarios.

## 1. Setup, isolated startup, and reset

From the repository root, use Python 3.10 or newer and install the runtime
dependencies, including the pinned PuLP/CBC solver:

```sh
python -m venv .venv
```

Activate with `source .venv/bin/activate` on macOS/Linux or
`.\.venv\Scripts\Activate.ps1` in Windows PowerShell, then:

```sh
python -m pip install -r requirements.txt
```

Start the real application with a fresh temporary SQLite database. Paste this
multiline command into the activated shell (macOS/Linux or PowerShell):

```sh
python -c "import tempfile
from pathlib import Path
from app import create_app
with tempfile.TemporaryDirectory(prefix='tech5-demo-') as directory:
    app = create_app({'DATABASE_PATH': Path(directory) / 'demo.db'})
    app.run(host='127.0.0.1', port=5001, debug=False)
"
```

Open **http://127.0.0.1:5001/**. Keep that terminal open; stop with **Ctrl+C**.
Normal shutdown removes the temporary database. Restart this command for a
fresh session. It uses the existing `create_app()` factory and does not touch
`instance/tech5_assignment.db`. Plain `python run.py` instead uses that persistent
database and port 5000, so use the isolated command for this walkthrough.
If port 5001 is occupied, select another port in the command and browser URL.

Choose **Administrator (Full Control)** in the top-right **Role** selector.
For a repeat within the same demo session:

1. Dashboard → **Clear All Solutions**; accept the confirmation.
2. Scenarios → **Load Standard Benchmark →**.
3. Check Dashboard: **Student Cohort 10**, **Active Projects 4**,
   **Total Max Capacity 12**, **Fixed Locks 0**; no previous runs remain.

The standard dataset also contains five skills. Loading a scenario replaces the
cohort and locks but retains old run/solution records while deleting their
assignments through foreign-key cascades. It is not a complete reset: clear
solutions first. Use these reset actions only in the isolated demo database.

## 2. Alternatives and a preference/skill-fit trade-off

1. Load the standard benchmark as above. On Dashboard select:
   - **Primary Objective Strategy:** Student Preference Maximization
     (Minimize Rank Regret).
   - **Distinct Alternatives to Retain:** 3 Distinct Solutions.
   - Click **Launch Optimization Run →** (`POST /runs/trigger`).
2. At `/runs/<run_id>`, expect **COMPLETED (3 Alternatives)**. All three use
   PREFERENCE; no-good cuts produce different allocations under that objective.
   Note this run's ID and **Alternative #1**, or keep its page in a browser tab.
3. Return to Dashboard without reloading data or adding locks. Select
   **Project Skill Fit Maximization (Highest Quality Delivery)** and **1 Solution**;
   launch again. Note this SKILL_FIT run's ID and Alternative #1.
4. Open **Compare** (`GET /compare`). Choose the earlier PREFERENCE Alternative
   #1 as **Baseline Solution (A)** and the SKILL_FIT Alternative #1 as
   **Comparison Solution (B)**. Labels include strategy and the run ID prefix.
   Click **Compare Allocations →**.
5. Show the skill-fit/rank deltas and changed-student table. Higher skill fit is
   better; lower mean preference rank is better. The cross-run warning is
   expected: here the cohort and locks were deliberately unchanged; only the
   objective and number of retained alternatives differed.

**Verified local example (2 November 2026):** PREFERENCE Alternative #1 displayed
**98.3%** skill fit and mean rank **1.00**; SKILL_FIT displayed **100.0%** and
**1.20**. This is a genuine trade-off: improving skill fit worsened preferences.
Two headless rehearsals produced these results. CBC can select other tied
SKILL_FIT optima, so do not promise mean rank 1.20 or particular student moves.
For completed optimal solves on this cohort, use the checkpoint **higher skill
fit and worse mean rank**, rather than exact secondary metrics. If it is absent
or the run reports WARNING/FAILED, stop and investigate before presenting.
Distinct alternatives are not a guarantee of Pareto optimality, despite older
wording still present in the application.

## 3. Recommendation

Return to the three-alternative PREFERENCE run → **View Recommendations →**
(`GET /recommendations/<run_id>`). This link is on the run overview, not the
solution details page.

Show one recommendation's **criteria, calculated evidence, and policy advice**,
plus the indicator comparison table. Explain that it compares alternatives
within this run, not across the two objective runs. Preference priority ranks
unranked count first, then mean/worst rank; skill priority uses skill fit and
soft gaps; egalitarian priority uses Gini, variance, and mean rank. Priorities
may recommend the same alternative or report ties; three different winners are
not required.

## 4. Fixed assignment and rerun

1. Open **Fixed Locks** (`GET /fixed-assignments`). In its form select:
   **Fredrik Berg (S06)**, **Cloud Data Pipeline & Lakehouse (P2 - Max 3)**,
   and **APPROVED**. Optionally enter a short demo reason.
2. Click **Lock Assignment Constraint** (`POST /fixed-assignments/new`).
   Confirm S06→P2 is listed. Saving a lock alone does not recalculate solutions.
3. Dashboard → select PREFERENCE and 3 Distinct Solutions →
   **Launch Optimization Run →**. In each alternative choose
   **Explore Allocations →**: S06 must be assigned to P2 with **FIXED LOCK**.
   This changes S06 from his original first-choice P3; do not promise particular
   changes to other students.

The solution table's separate **Lock & Rerun** action pins that row's existing
student/project pair and immediately reruns with default PREFERENCE/3 settings.
It cannot select an arbitrary new project. The explicit Fixed Locks form above
makes the changed input clear and avoids relying on which tied allocation appears.

## 5. Infeasible case

After completing the comparisons:

1. Dashboard → **Clear All Solutions**; confirm.
2. Scenarios → **Load Infeasible Capacity Scenario →**
   (`POST /load-scenario/infeasible`).
3. Dashboard shows **10 students**, **6 maximum places**, and **Capacity Deficit**.
4. Launch PREFERENCE/3 again. The run must show **INFEASIBLE**, zero solutions,
   and: `Insufficient overall capacity: total cohort size (10) exceeds aggregate
   maximum project capacity (6).`

Validation detects this before optimization; no partial allocation is offered.
To repeat the whole demonstration, follow the reset steps in section 1.
The existing fixed and contradictory-lock scenarios remain available but are
not needed for this concise four-requirement demonstration.

## Verification and presentation rehearsal

On 2 November 2026, the sequence above was checked twice through Flask's test
client with the real AssignmentEngine/CBC and disposable SQLite storage:
three PREFERENCE alternatives, a SKILL_FIT trade-off, comparison and recommendation
pages, three rerun alternatives preserving S06→P2, capacity-deficit diagnostics,
reset, and temporary-database cleanup all passed. This is application-level
verification, not a manual browser rehearsal. The isolated startup command
also served a live HTTP 200 response at `/scenarios` on port 5001 and shut down
cleanly with Ctrl+C (SIGINT). The existing tests in
`test_team_b_application.py`, `test_component_integration.py`,
`test_visualization_component.py`, and `test_process_persistence.py` returned
**78 passed in 4.09s** using `pytest -v -p no:cacheprovider` (modules under
`tests/`, with `PYTHONDONTWRITEBYTECODE=1`).

Before presenting, rehearse in the actual browser/environment: confirm CBC can
run, links/dropdowns are usable, confirmation dialogs appear, metrics and tables
are readable, run IDs identify the intended comparison, and the isolated server
starts/stops correctly. Do not use solver tie order or generated UUIDs as fixed
presentation checkpoints. See [testing and quality](testing_and_quality.md) for
existing automated-suite commands.
