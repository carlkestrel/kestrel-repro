# R2 State Model

## Project States

```
DETECTED → INTERVIEWING → PLANNED → WAITING_CONFIRMATION → RUNNING
                                                    ↓
                                             WAITING_DECISION
                                                    ↓
                                               PAUSED
                                                    ↓
                                            BLOCKED
                                                    ↓
                                          COMPLETED | STOPPED
```

| State | Description |
|---|---|
| `DETECTED` | New project discovered |
| `INTERVIEWING` | Gathering project metadata |
| `PLANNED` | Plan written and saved |
| `WAITING_CONFIRMATION` | Awaiting human confirmation |
| `RUNNING` | Active execution |
| `WAITING_DECISION` | Plan changed or authorization invalidated |
| `PAUSED` | User-paused |
| `BLOCKED` | Blocked (conflict, error) |
| `COMPLETED` | All tasks passed |
| `STOPPED` | User-stopped |

## Task States

```
PENDING → READY → WAITING_APPROVAL → APPROVED → RUNNING → VERIFYING → PASSED
                ↓                   ↓
              REJECTED          REJECTED
                ↓                   ↓
              WAIVED             WAIVED
                ↓                   ↓
             (terminal)        (terminal)

PENDING → BLOCKED → READY → ...
READY → RUNNING → FAIL → RETRY_WAIT → READY
READY → FAIL → BLOCKED
VERIFYING → PASSED | FAILED → RETRY_WAIT | BLOCKED
```

| State | Description |
|---|---|
| `PENDING` | Not yet eligible (deps not met) |
| `READY` | Eligible to run |
| `WAITING_APPROVAL` | Awaiting human decision |
| `APPROVED` | Human approved, ready to run |
| `REJECTED` | Human rejected |
| `WAIVED` | Human waived this task |
| `RUNNING` | Subprocess active |
| `VERIFYING` | Acceptance tests running |
| `PASSED` | Evidence verifier confirmed |
| `FAILED` | Task failed |
| `RETRY_WAIT` | Waiting before retry |
| `BLOCKED` | Blocked by gate or human |
| `LEGACY_UNVERIFIED` | Migrated task, PASS not confirmed |

## Gate States

| State | Description |
|---|---|
| `LOCKED` | Gate not yet passed |
| `UNLOCKED` | Gate passed |
| `BLOCKED` | Gate blocked |

Gates cannot be manually set to `UNLOCKED`; they must be transitioned via task completion.

## State Transition Rules (Fail-Closed)

Any transition not listed below is **forbidden**.

| From | To | Who |
|---|---|---|
| PENDING | READY | system |
| READY | RUNNING | system |
| READY | WAITING_APPROVAL | system |
| READY | REJECTED | human |
| READY | FAIL | system |
| READY | BLOCKED | human/system |
| WAITING_APPROVAL | APPROVED | human |
| WAITING_APPROVAL | REJECTED | human |
| WAITING_APPROVAL | WAIVED | human |
| APPROVED | RUNNING | system |
| RUNNING | VERIFYING | system |
| RUNNING | FAIL | system |
| RUNNING | READY | system |
| VERIFYING | PASSED | evidence_verifier/acceptance |
| VERIFYING | FAIL | system |
| FAIL | RETRY_WAIT | system |
| RETRY_WAIT | READY | system |
| FAIL | BLOCKED | system |
| BLOCKED | READY | human/system |
| LEGACY_UNVERIFIED | PASSED | evidence_verifier |
| LEGACY_UNVERIFIED | FAIL | system |
| LEGACY_UNVERIFIED | BLOCKED | system |

**Key rules**:
- `PASSED` is terminal — no transitions out
- `WAIVED` is terminal — no transitions out
- `REJECTED` is terminal — no transitions out
- `PASSED` can only be set by `evidence_verifier` or `acceptance` (not by human)