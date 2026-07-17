# OSTAR — Overnight Soak Test and Controlled Auto-Repair

**Component**: `scripts/ostar/`
**Entry point**: `reproctl soak <subcommand>`
**CLI**: `scripts/ostar/cli.py`
**Engine**: `scripts/ostar/soak_engine.py`

---

## Overview

OSTAR runs unattended overnight stress tests on the dl-paper-repro plugin. It cycles through TEST → DETECT → REPRODUCE → CLASSIFY → REPAIR → TARGETED_TEST → REGRESSION_TEST → RESUME_SOAK until a termination condition fires.

**Default window**: 8 hours, Asia/Singapore timezone.
**Auto-repair level**: `safe` (only known-safe error classes).

---

## Quick Start

```bash
# 1. Pre-flight rehearsal (30 minutes)
reproctl soak plan --project . --duration 30m

# 2. Full overnight soak (8 hours)
reproctl soak start --project . --duration 8h --auto-repair safe

# 3. Check status
reproctl soak status --project .

# 4. View morning report
reproctl soak report --project . --format markdown
```

---

## Architecture

```
soak_engine.py       # Core loop (forked subprocess, heartbeat thread)
├── guard.py         # Pre-flight protection checks
├── hardware_monitor.py  # GPU/CPU/disk monitoring
├── test_suites.py   # 7 stress test suites
├── repair_node.py  # Per-bug SOAK-BUG-xxx repair node
├── exit_validator.py    # Stability acceptance criteria
├── reporter.py      # Morning report generation
├── soak_state.py   # SQLite + atomic JSON state
└── cli.py          # argparse CLI (7 subcommands)
```

### State directory layout

```
soak/
├── soak_manifest.json      # Run metadata (run_id, config)
├── current_state.json      # Latest state (atomic write)
├── heartbeat.json          # Last heartbeat (atomic write, every 30s)
├── soak.sqlite3           # WAL-journal SQLite DB
├── nodes/                 # Per-SOAK-BUG result JSON
├── failures/              # FAIL-XXXX.json evidence
├── repairs/               # Per-bug repair evidence
├── logs/                  # Per-PID soak log files
├── metrics/               # Cycle metrics CSV
├── checkpoints/           # Atomic ckpt_NNNNNN.json
└── reports/               # Morning reports
```

---

## Configuration

### CLI flags

| Flag | Default | Description |
|---|---|---|
| `--duration` | `8h` | Total soak duration (8h, 480m, 28800s) |
| `--start-time` | now | Start time in HH:MM or ISO format |
| `--end-time` | computed | End time (overrides `--duration`) |
| `--timezone` | Asia/Singapore | Timezone |
| `--auto-repair` | `safe` | none / safe / full |
| `--max-repairs` | 10 | Max total repairs |
| `--max-retries` | 3 | Max attempts per bug |
| `--gpu-temperature-limit` | 87°C | Critical GPU temp |
| `--disk-reserve` | 10 GB | Min free disk |
| `--dry-run` | false | Run one cycle only |

### Auto-repair levels

| Level | CODE | CONFIG | RESOURCE | STATE | CLI | CHECKPOINT | FIXTURE | METRIC | ENV | PROTOCOL | DATA |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `none` | — | — | — | — | — | — | — | — | — | — | — |
| `safe` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | BLOCKED | BLOCKED |
| `full` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | BLOCKED | BLOCKED |

`MODEL`, `LOSS`, `SCHEDULER` are always BLOCKED.

---

## Test Suites

| Suite | What it tests |
|---|---|
| `CI_STRESS` | pytest runs repeated 3× to detect flakiness |
| `SCHEDULER_STRESS` | reproctl start/pause/resume/stop cycle |
| `GPU_STRESS` | Real forward/backward/eval loop (≤100 steps) |
| `BATCH_BOUNDARY` | paper_batch, recommended_batch±1, P95, max |
| `DATALOADER_STRESS` | num_workers ∈ {0,2,4}, prefetch, pin_memory |
| `METRIC_CONSISTENCY` | Deterministic metric recompute (2 identical runs) |
| `RESOURCE_LEAK` | GPU/CPU RAM + file handle growth over 10 samples |

---

## Termination Conditions

1. `end_time_reached` — wall-clock deadline exceeded
2. `max_repairs_reached` — `max_repairs` exhausted
3. `same_bug_consecutive_failures` — same bug fails 3× repair attempts
4. `p0_unresolved` — BLOCKED class error (PROTOCOL/DATA) detected
5. `git_workdir_unsafe` — dirty diff cannot be safely isolated
6. `gpu_temperature_exceeded` — critical GPU temp exceeded
7. `disk_space_below_reserve` — free disk < `disk_reserve_gb`
8. `state_file_corrupt` — checkpoint JSON unparseable
9. `consecutive_agent_crashes` — 3 OSTAR internal crashes

---

## Acceptance Criteria (11 gates)

| # | Criterion | Required? | Pass threshold |
|---|---|---|---|
| 1 | P0 unresolved = 0 | ✅ | 0 |
| 2 | P1 unresolved = 0 | ✅ | 0 |
| 3 | Core CI pass rate | ✅ | 100% |
| 4 | Last 2h no new errors | ✅ | True |
| 5 | Metric flaky rate | ✅ | 0% |
| 6 | Scheduler recovery rate | ✅ | 100% |
| 7 | GPU batch success rate | ✅ | 100% |
| 8 | No memory leak | ✅ | No growth |
| 9 | No orphan processes | ✅ | 0 |
| 10 | No stub/hardcoded metrics | ✅ | Clean |
| 11 | All repairs have regression tests | ❌ | — |

### Verdict mapping

| Acceptance result | Verdict |
|---|---|
| All required PASS | `SOAK_VERIFIED` |
| ≤2 failed, last 2h stable, CI ≥95% | `REPAIRED_BUT_NOT_SOAK_VERIFIED` |
| >2 required failures | `FAILED_WITH_UNRESOLVED_BUGS` |
| BLOCKED class detected | `BLOCKED_REQUIRES_REVIEW` |
| Hardware limit exceeded | `ABORTED_FOR_HARDWARE_SAFETY` |

---

## Anti-Fake-Fix Rules

OSTAR forbids these workarounds (Section V):

- Deleting or skipping tests
- Weak assertions (tolerance too large)
- Catching exceptions and returning success
- Increasing timeouts to hide deadlocks
- Mocking real model paths
- Changing target metrics
- Ignoring non-zero exit codes

Detection: after every repair, CI is re-run. If it does not improve → FAKE_FIX_ROLLBACK.

---

## Recovery on Restart

OSTAR is fully recoverable after `reproctl soak start`:

1. Read `soak_manifest.json` → get `run_id`
2. Check last heartbeat age
3. Identify incomplete cycles from `cycles` table
4. Verify processes still alive via PIDs in DB
5. Resume from last valid checkpoint
6. Never re-run PASSed tests

---

## Hardware Safety

OSTAR does not use training parameters to "fix" hardware issues.

| Condition | Action |
|---|---|
| GPU temp ≥ 82°C | Warning logged |
| GPU temp ≥ 87°C | Pause GPU tests, wait to cool |
| 3 consecutive temp exceedances | Stop GPU stress tests |
| Disk free < 10 GB | Abort with HARDWARE_SAFETY verdict |
| Training process detected | Warning logged (not killed) |

Vendor max temps: NVIDIA = 83°C, AMD = 90°C.

---

## Cursor Commands

| Command | Maps to |
|---|---|
| `Repro: Plan Overnight Soak` | `reproctl soak plan` |
| `Repro: Start Overnight Soak` | `reproctl soak start` |
| `Repro: Pause Soak` | `reproctl soak pause` |
| `Repro: Resume Soak` | `reproctl soak resume` |
| `Repro: Stop Soak` | `reproctl soak stop` |
| `Repro: View Soak Status` | `reproctl soak status` |
| `Repro: Open Morning Report` | `reproctl soak report` |
| `Repro: Run Soak Rehearsal` | `reproctl soak plan --duration 30m` |
