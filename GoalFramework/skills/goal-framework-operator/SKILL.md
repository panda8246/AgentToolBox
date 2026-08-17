---
name: goal-framework-operator
description: Operate repositories initialized with Goal Framework safely and consistently. Use when Codex needs to inspect goal status, create a delivery or exploration goal, record a checkpoint, mark completion criteria, archive a completed goal, diagnose framework drift, or reconcile docs/CURRENT.md with goals/active. Also use for requests such as “继续当前目标”, “新建/完成/归档目标”, “检查 goal framework”, or work explicitly referencing .goal-framework.json or a goals/active file. Do not use for Codex's native /goal runtime unless the request also involves repository Goal Framework files.
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
3. Use `new` only for work needing independent progress, exploration, or acceptance. Do not create a goal for a small one-turn edit.
4. Use `checkpoint` after meaningful, reusable progress. Record facts and evidence, not chat history.
5. Verify every completion condition before marking it satisfied.
6. Run `complete` only after every condition is checked. Provide concrete evidence and a concise result.
7. Run `doctor` again after mutations and report any remaining warnings.

## Operations

Inspect without changing files:

```text
python "$GF" --project . status
python "$GF" --project . doctor
python "$GF" --project . doctor --strict
```

Create a goal. Use a lowercase ASCII slug; pass each verifiable condition separately:

```text
python "$GF" --project . new \
  --title "Add export support" \
  --slug add-export-support \
  --type delivery \
  --purpose "Let users export validated data." \
  --condition "CSV export passes its integration tests" \
  --condition "User documentation describes the workflow"
```

Use `--type exploration` when the output is a decision or evidence-backed conclusion.

Record a checkpoint. `--done` appends durable accomplishments; supplied current/blocked/next values replace those lists. Use the corresponding `--clear-*` flag to empty a list. `--satisfy` uses one-based completion-condition indexes:

```text
python "$GF" --project . checkpoint 2026-08-17-add-export-support.md \
  --done "Implemented streaming CSV writer" \
  --in-progress "Add integration coverage" \
  --next "Run the full test suite" \
  --satisfy 1
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
- Never use `complete` to bypass unchecked conditions. Update or remove an invalid condition only after discussing the scope change with the user.
- Do not invent evidence, dates, progress, blockers, or conclusions.
- Stop on ambiguous goal references, malformed managed files, lock contention, or archive-name collisions.
- Keep repository Goal Framework state distinct from Codex `/goal`: repository files are durable shared state; `/goal` controls one long-running Codex execution.
