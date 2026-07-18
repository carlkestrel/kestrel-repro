---
description: Toggle between plan / reproduce / evolve modes for the dl-paper-repro project.
---

# /repro-contract

> **Discoverable Cursor command** — bound to `commands/repro-contract.md`. Use
> it whenever you want to (a) inspect the current project mode, (b) request
> a mode switch, or (c) read the rules a mode implies.

## Usage

```
/repro-contract                    # show current mode + flags
/repro-contract status              # same as above
/repro-contract set <mode>          # request a switch (writes a D-row)
/repro-contract help                # this file
```

Where `<mode>` ∈ {`plan`, `reproduce`, `evolve`}.

## What this command does

1. Reads `.repro/repro_audit/STATE.json` (managed by `scripts/reproctl.py`).
2. Prints current `project_mode` and the resolved `control_flags`.
3. For `set <mode>`:
   - Loads `templates/control_flags.md` (canonical flag schema).
   - Calls `set_project_mode(new_mode)` which:
     - Validates the transition against the rules below.
     - Writes a row to `DECISION_LOG.md`.
   - If `HUMAN_CHECKPOINT=true` (default), **blocks** the transition
     unless a human approver is recorded on a prior `D__` row.

## Mode transition rules

| From      | To          | Allowed? | Notes |
|-----------|-------------|----------|-------|
| `plan`    | `reproduce` | yes      | Requires human approval row referencing `research_contract.md` |
| `reproduce` | `evolve`  | yes      | Requires a `P5_review` PASS row + human approval |
| `reproduce` | `plan`    | yes (rollback) | Allowed; must record reason |
| `evolve`  | `reproduce` | yes | Allowed; must record reason |
| any       | other      | no       | Only the three canonical modes exist |

## Output

After a successful switch, you will see:

```
[repro-contract] mode = reproduce
[repro-contract] flags = { HUMAN_CHECKPOINT: true, AUTO_RETRY: false, ALLOW_NETWORK: true, REQUIRE_GIT_PIN: true }
[repro-contract] decision = D007 → DECISION_LOG.md
```

## Failure modes

- `Gate 'human_checkpoint' FAILED` → you tried a `plan→reproduce` switch
  without a prior approval row. Open `templates/research_contract.md`, fill
  it, and create the row first.
- `mode 'foo' not recognized` → only `plan` / `reproduce` / `evolve` are valid.
- `permission denied writing .repro/repro_audit/` → check ownership of
  `.repro/` (should be the same user as `reproctl.py`).

## Files

- `scripts/reproctl.py` — implementation
- `templates/control_flags.md` — flag defaults
- `templates/research_contract.md` — required before `plan→reproduce`
- `.repro/repro_audit/STATE.json` — runtime state
- `.repro/repro_audit/DECISION_LOG.md` — append-only history