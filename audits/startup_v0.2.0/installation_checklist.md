# Installation Checklist (v0.2.0)

A plugin user installs the dl-paper-repro plugin once and then runs
`reproctl start` against any project root. This checklist is the
minimum to verify.

## Plugin-side (one-time)

- [ ] Plugin lives at `<CURSOR_PLUGINS>/local/dl-paper-repro/`
- [ ] `.cursor-plugin/plugin.json` declares `version: "0.2.0"`
- [ ] `scripts/reproctl.py` dispatches new subcommands to
      `scripts/startup/cli.py` and keeps legacy subcommands working
- [ ] `scripts/reproctl` (no `.py`) is executable (`chmod +x`) and
      has shebang `#!/usr/bin/env python3`
- [ ] `commands/repro-start.md`, `repro-doctor.md`,
      `repro-status.md`, `repro-resume.md`, `repro-stop.md`,
      `repro-verify.md` all exist and are ≤ 30 lines each

## Project-side (per-project, performed automatically by `start`)

- [ ] `.repro/config.yaml` (optional) — strict, optimized,
      diagnose, test, extend (mode is `strict` by default)
- [ ] `.repro/startup/{startup_state.json, startup.log,
      doctor_report.json, startup_summary.md}` created
- [ ] `.repro/execution/{plan_snapshot.md, task_graph.yaml,
      execution_state.json, task_journal.jsonl,
      requirement_traceability.csv, checkpoints/, heartbeats/,
      evidence/}` created
- [ ] `.repro/run.lock` created and held for the duration of the
      startup pipeline

## Verifying

```bash
python scripts/reproctl.py version
python scripts/reproctl.py --help
cd <project>
python scripts/reproctl.py doctor --project <PROJECT_ROOT> --plan <PLAN_PATH>
python scripts/reproctl.py start  --project <PROJECT_ROOT> --plan <PLAN_PATH> --dry-run
python scripts/reproctl.py start  --project <PROJECT_ROOT> --plan <PLAN_PATH>
```

## What the install does NOT do

- Does NOT install dependencies
- Does NOT download datasets
- Does NOT launch training
- Does NOT modify the primary repository
- Does NOT touch user data outside `.repro/`

## Optional but recommended

```bash
python -m pytest tests/test_startup.py -q
```
