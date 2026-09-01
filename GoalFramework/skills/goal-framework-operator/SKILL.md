---
name: goal-framework-operator
description: Operate repositories initialized with Goal Framework safely and consistently. Use when Codex needs to inspect goal status, create a delivery or exploration goal, attach or detach a technical plan, record a checkpoint, mark completion criteria, archive a completed goal, diagnose framework drift, or reconcile docs/CURRENT.md with goals/active. Also use for requests such as “继续当前目标”, “关联技术方案”, “新建/完成/归档目标”, “检查 goal framework”, or work explicitly referencing .goal-framework.json or a goals/active file. Do not use for Codex's native /goal runtime unless the request also involves repository Goal Framework files.
---

# Goal Framework Operator

Use the bundled Python command for deterministic file changes. Keep judgment in the conversation: understand the project, draft meaningful content, verify evidence, and then call the command.

## Command

Set `GF` to this skill's `scripts/goal-framework` path, then invoke:

```text
python "$GF" --project <project-root> <subcommand> [arguments]
```

Treat `goal-framework` as the command name. Do not shorten it to `goal`, because `/goal` is a separate Codex runtime feature.

If `python` is unavailable, locate a Python 3.10+ interpreter and use it explicitly. Do not rewrite the command in another language.

## Workflow

1. Run `goal-framework doctor` before the first mutation in a session.
2. Read `docs/PROJECT.md`, `docs/CURRENT.md`, and the relevant active goal before deciding what to change.
3. Read every technical plan linked by the goal, in list order, before coding. If a plan conflicts with the goal or current code/configuration, report it and reconcile the documents before implementation.
4. Treat ordinary discussion, review, or brainstorming as no authorization to write a technical plan. When the user explicitly asks to save one, follow the persistence workflow below.
5. Use `new` only for work needing independent progress, exploration, or acceptance. Do not create a goal for a small one-turn edit.
6. Use `checkpoint` after meaningful, reusable progress. Record facts and evidence, not chat history.
7. For complex goals, split broad completion conditions into nested, independently verifiable leaf conditions. Parent conditions summarize their children and are satisfied automatically only when every child is satisfied.
8. Verify every leaf completion condition before marking it satisfied.
9. Run `complete` only after every leaf condition is checked. Provide concrete evidence and a concise result.
10. Run `doctor` again after mutations and report any remaining warnings.

## Technical plan persistence

When the user explicitly asks to save, persist, record, or archive a technical plan (or clearly expresses equivalent intent):

1. Distill the agreed plan into a standalone document. Preserve key decisions, implementation steps, validation, and unresolved items; do not copy the full chat transcript.
2. Create `docs/technical-plans/` if needed and write a UTF-8 Markdown file named `docs/technical-plans/<descriptive-name>.md`. The body remains free-form and is not parsed by Goal Framework.
3. Do not overwrite an existing document unless the user explicitly asked to update it. Choose a new descriptive filename on an unintended collision.
4. If one active goal is clearly identified, run `plan attach` after the file is written. If no goal is known or the reference is ambiguous, do not guess: report that the document is saved but unlinked and ask which goal to use.
5. Run `goal-framework doctor`, then report the document path, linked goal if any, and validation result.

## Operations

Inspect without changing files:

```text
python "$GF" --project . status
python "$GF" --project . doctor
python "$GF" --project . doctor --strict
```

Create a goal. Use a lowercase ASCII slug; pass each verifiable condition separately. Prefix a condition with `> `, `>> `, and so on to nest it under the preceding condition:

```text
python "$GF" --project . new \
  --title "Add export support" \
  --slug add-export-support \
  --type delivery \
  --purpose "Let users export validated data." \
  --condition "Export is ready" \
  --condition "> CSV export passes its integration tests" \
  --condition "> User documentation describes the workflow"
```

Use `--type exploration` when the output is a decision or evidence-backed conclusion.

Attach an existing Markdown document under `docs/technical-plans/`. The document must already exist; repeat the command to attach more than one plan:

```text
python "$GF" --project . plan attach \
  2026-08-17-add-export-support.md \
  docs/technical-plans/export-support.md
```

Detach the link without deleting the technical plan. This also works when the linked document is already missing:

```text
python "$GF" --project . plan detach \
  2026-08-17-add-export-support.md \
  docs/technical-plans/export-support.md
```

Record a checkpoint. `--done` appends durable accomplishments; supplied current/blocked/next values replace those lists. Use the corresponding `--clear-*` flag to empty a list. `--satisfy` uses one-based hierarchical indexes such as `1.2`; only leaf conditions may be satisfied directly, and parent checkboxes are updated automatically:

```text
python "$GF" --project . checkpoint 2026-08-17-add-export-support.md \
  --done "Implemented streaming CSV writer" \
  --in-progress "Add integration coverage" \
  --next "Run the full test suite" \
  --satisfy 1.1
```

Archive only after validation:

```text
python "$GF" --project . complete 2026-08-17-add-export-support.md \
  --result "Export support shipped with documentation." \
  --evidence "pytest: 84 passed" \
  --evidence "Manual CSV round-trip verified"
```

## Safety rules

- Never hand-edit filenames or move goals when the command can do it.
- Never create or revise a technical plan unless the user explicitly requests it. `plan attach/detach` manages links only and never writes the plan body.
- Never silently implement around a conflict between a linked technical plan, the goal, and current code or configuration.
- Never use `complete` to bypass unchecked conditions. Update or remove an invalid condition only after discussing the scope change with the user.
- Do not invent evidence, dates, progress, blockers, or conclusions.
- Stop on ambiguous goal references, malformed managed files, lock contention, or archive-name collisions.
- Keep repository Goal Framework state distinct from Codex `/goal`: repository files are durable shared state; `/goal` controls one long-running Codex execution.
