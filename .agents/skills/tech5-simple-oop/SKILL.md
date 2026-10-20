---
name: tech5-simple-oop
description: Build, review, test, and explain the TECH5 student-to-project assignment application using simple object-oriented Python and the existing Flask, Jinja, and SQLite structure. Apply to programming and design decisions in this project.
---

# Simple object-oriented programming for TECH5

Use code that the student team can read, explain, test, and change. Make
object-oriented design a central part of the application. These are the
user's project coding preferences; do not present them as extra instructor
requirements or claim that the team already understands unfamiliar code.

## Languages and tools

- Use Python for domain objects, business rules, validation, analytical
  calculations, assignment logic, and database access.
- Keep Flask and Jinja for the existing web application. Use HTML and CSS
  for its pages. Add small amounts of JavaScript only when the interface
  needs them and explain their purpose.
- Use SQLite and parameterized SQL through the existing repositories.
  Keep database values separate from SQL text.
- Use pytest for automated checks and Git branches and pull requests for
  collaboration.
- Prefer the standard library and installed dependencies. Explain the need
  and trade-offs before adding a dependency. A justified solver library
  for the approved assignment method can be simpler than a custom solver.
- Preserve the starter's single-process application and Python component
  contract. Work within its structure rather than introducing another
  framework, language, API service, or separate application by default.

## Object-oriented design is the priority

- Reuse the existing domain classes, including `Student`, `Project`,
  `Skill`, `Preference`, and the run and solution objects.
- Give each class one clear responsibility. Explain what data it holds,
  what its methods do, and which other objects it works with.
- Put behaviour with the object responsible for it. For example, the
  engine coordinates assignment work and a repository saves and loads
  records. Keep calculations and database queries out of HTML templates.
- Prefer objects collaborating through simple method calls. Pass required
  collaborators through constructors where the starter supports this,
  making it possible to substitute a test repository or mock engine.
- Retain useful existing dataclasses, abstract interfaces, and strategy
  inheritance. Explain these when relevant instead of removing them merely
  because their syntax is unfamiliar.
- Introduce a class when it represents a meaningful concept or owns related
  data and behaviour. Avoid giant classes that do everything and extra
  inheritance layers without a concrete need.
- Keep small validation and mathematical helpers as functions when they
  need no persistent object state. Do not wrap every function in a class
  simply to make the project look more object-oriented.

## Python constructs to use

Prefer familiar, explicit code:

- Named variables, ordinary functions, classes, constructors, and methods.
- `if` / `elif` / `else`, `for` loops, and straightforward `return` statements.
- Lists, dictionaries, sets, and tuples where their purpose is clear.
- Simple type hints that match the starter. Explain that type hints do not
  perform runtime input validation.
- Short comprehensions when they are easy to read; use a loop for several
  conditions or steps.
- `with` for managed resources and transactions, and specific exceptions
  for failures the application can explain or recover from.

Use descriptive names such as `student`, `project`, and `max_capacity`.
Use short functions with a clear input, result, and purpose. Follow existing
formatting and docstring conventions. Comments should explain reasons or
assumptions; avoid comments that merely repeat each line of Python.

Avoid clever one-liners, nested comprehensions, obscure lambdas, metaclasses,
dynamic code generation, and new concurrency or abstraction frameworks by
default. If a more advanced construct solves a real project problem, explain
why the simpler approach is insufficient and keep its use focused. Preserve
working starter features without unrelated rewrites.

Do not hide errors with a broad catch-and-ignore block. Validate types and
ranges before arithmetic or comparisons that could fail; return the errors,
warnings, and outcomes expected by the existing contract.

## Keep the course learning areas visible

| Learning area | How to express it in this project |
| --- | --- |
| Object-oriented design | Domain objects, focused classes, repository objects, and the engine's existing interface and strategies. |
| Business logic | Clear rules in the domain and engine layers, independent of Flask request objects and templates. |
| Analytical reasoning | Documented constraints, scores, and fairness measures with small worked examples. |
| Database interaction | Repository methods, parameterized SQL, integrity rules, and transactions. |
| Visualization | Understandable Flask/Jinja pages that explain assignments, warnings, and trade-offs. |
| Testing | Small synthetic examples with clear inputs and expected outcomes, plus contract and integration checks where relevant. |
| Integration | Team A and Team B communicate through the existing contract; Team A can keep using the mock engine. |
| Collaborative development | Focused changes on a feature branch, honest test evidence, and review of shared code by both teams. |

These areas guide the application as a whole. A small change does not need
to demonstrate all eight or introduce a new class, test layer, or diagram.

## Teaching and implementation workflow

Read the relevant code and tests before editing. Paths below are relative to
the repository root. Check actual implementations before relying on starter
documentation that describes unfinished behaviour.

1. Explain the rule or behaviour being changed in plain language. Name the
   files involved and give one concrete input and expected result.
2. Make one coherent change that the student can follow. Explain unfamiliar
   syntax and how the important classes or functions cooperate.
3. For a behaviour change, add or update a meaningful test, then run the
   relevant existing checks. Report the observed result. Use ordinary setup,
   function calls, and assertions before introducing complicated fixtures.
4. Update the affected documentation. For validation work, use
   [the checklist](../../../docs/input_output_validation_checklist.md) and
   mark a case done only when its intended response is agreed, implemented,
   and supported by passing tests. Expected failures are unfinished work.
5. Follow [the Git workflow](../../../docs/git_workflow.md). Preserve
   teammates' changes and coordinate shared contract, model, and database
   changes. Do not invent commits, approvals, test results, or contributions.

Record unresolved policies such as preference ties, partial allocation,
mandatory skill coverage, and scoring weights as proposals. Obtain the
required instructor approval before treating an assignment method as the
baseline. Simplicity must preserve hard constraints and distinguish invalid
input, proven infeasibility, search limits, and operational failures.

After a meaningful change, explain what changed, why its location makes
sense, and how it was checked. Offer a small learning checkpoint when useful;
do not turn every edit into a compulsory quiz or ask permission for routine
work already authorized by the user.

## Explain approval requests in simple language

Ask for approval only when permission is actually needed. Continue routine
work that the user has already authorized. Before a commit, explain the
changes and tests so the student can understand what will be recorded.

Make each approval question understandable on its own. Briefly explain:

- What action will happen and why it helps the current task.
- Why approval is needed now, such as access to a temporary folder or
  permission to publish commits. Name the actual restriction rather than
  implying that the user must approve the programming rule or algorithm.
- Which files, data, branch, or external service the action affects.
  Explain a material consequence, such as publishing work on GitHub.

Use everyday words. For example, say "temporary test folders" instead of
"escalated pytest execution". If a technical word is needed, explain it.
Put this explanation in the actual approval question, including a tool's
approval prompt when that is where the user must answer.

Example for a test run that needs extra file access:

> May I run the full tests with access to temporary test folders? This
> checks whether the capacity change works with the rest of the app.
> The tests create separate databases in those folders.

Example when publishing commits actually requires approval:

> May I push these commits to `teamB/input_validation` on GitHub so the
> team can review them? This publishes the committed changes on that branch.

These examples do not authorize those actions. Reuse permission already
given for the same action and scope. If a new request is required, explain
what changed. If a skill or repository rule requires approval, link the
exact file and quote the relevant instruction. If an automatic approval
check rejects an action, explain which action was rejected and its stated
reason in simple language.
