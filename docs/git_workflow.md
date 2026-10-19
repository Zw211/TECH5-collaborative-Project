# Git Workflow Agreement

Team A (visualization) and Team B (engine), four members in total.

## Repository

- One shared repo: `Zw211/TECH5-collaborative-Project`, a fork of the
  instructor starter `jcgoez/TECH5-collaborative-Project`.
- All four members are collaborators. No personal forks.
- The `upstream` remote is the instructor starter. Updates from it are merged
  through a normal branch + PR, never with GitHub's "Sync fork" button.
- When opening a PR, set the base repository to
  `Zw211/TECH5-collaborative-Project`. GitHub defaults forks to the parent.

## Branching (GitHub flow)

- `main` is protected. Nobody pushes to it directly.
- Short-lived branches, 1 to 3 days each: `teamA/<feature>`,
  `teamB/<feature>`.
- Update your branch from `main` daily.

## Pull requests

- 1 approval from your own team.
- Plus 1 approval from the other team when shared paths are touched
  (see `.github/CODEOWNERS`).
- `python -m pytest -q` must pass.
- Merge with "Create a merge commit" (no squash) to preserve history.

## Contract changes

Any change to `app/contract/contract.py` or `app/domain/models.py` is
announced to both teams before the PR is opened.

## Indicator keys

The UI (templates) and `app/engine/recommendations.py` read these keys from
`Solution.indicators`. Renaming or removing one is a contract change.

| Group | Keys read |
| --- | --- |
| `fairness` | `mean_rank`, `worst_rank`, `unranked_count`, `unranked_pct`, `rank_gini`, `rank_variance` |
| `efficiency` | `mean_skill_fit`, `unmet_soft_requirements_count` |
| `capacity` | `projects[<project_id>]` with `assigned_count`, `min_capacity`, `max_capacity`, `utilization_pct` |

Read by:

- `recommendations.py`: all `fairness` keys except `unranked_pct`, plus both
  `efficiency` keys.
- `run_detail.html`: `mean_skill_fit`, `mean_rank`, `worst_rank`,
  `rank_gini`, `unranked_count`.
- `solution_detail.html`: all of the above, plus `unranked_pct`,
  `rank_variance`, `unmet_soft_requirements_count` and `capacity.projects`.
- `mocks.py` (comparison): `mean_skill_fit`, `mean_rank`, `rank_gini`.

Also produced but not read by the UI or recommendations (only `feasibility`
and `capacity.overall_utilization_pct` are asserted in tests):
`feasibility.*`, `fairness.rank_distribution`,
`efficiency.total_skill_fit_sum`, `capacity.total_assigned`,
`capacity.total_capacity`, `capacity.overall_utilization_pct`.

## Open question

Who owns `app/engine/recommendations.py`? It sits under Team B's
`app/engine/` but depends on the indicator keys above, which the UI also
reads. To resolve with Team B.
