# Project Memory

> **Two-section** canonical knowledge store for the dl-paper-repro project.
> Section 1 captures *project-level* experience (decisions made, traps
> hit, what worked for *this* paper). Section 2 captures *global*
> knowledge (cross-project best practices that apply regardless of which
> paper is being reproduced).

> **Why two sections?** Section 1 is project-specific and grows with each
> decision row; Section 2 is curated by humans and is shared across
> projects. The line between them is: if it's a fact about *this* paper
> or *this* repo, it goes in §1. If it's a reusable lesson that would
> help the next paper too, it goes in §2.

---

## 1. Project-Level Experience

### 1.1 Decisions (chronological, mirrors DECISION_LOG.md summary)

| Decision id | Phase | Type | One-line summary |
|---|---|---|---|
| D000 | P1_mode_contract | note | project_mode='reproduce' default |
| D__ | (add per row) | | |

### 1.2 Traps hit (what went wrong, and the fix)

| Date | Symptom | Root cause | Fix |
|---|---|---|---|
| (add row per real failure) | | | |

### 1.3 What worked (keep doing)

- (e.g., "Pre-filling `research_contract.md` from `repro_spec.yaml` saved ~30 min of spec translation.")

### 1.4 What didn't work (avoid next time)

- (e.g., "Don't try to auto-tune batch size during M4; the LR-scaling interaction masked a real bug in the optimizer.")

### 1.5 Project-specific facts

- **Paper**: (title, arXiv id, target table)
- **Repo**: (URL, commit pinned)
- **Dataset**: (name, version, size)
- **Hardware**: (GPU, VRAM, drivers)
- **Wall-clock so far**: (cumulative)

---

## 2. Global Knowledge

> **Curated by humans**. Promote a fact from §1.4 to here *only* when it
> is observed to apply across at least one other project. Each entry must
> be ≤ 3 sentences and end with a citation of where it was observed.

### 2.1 Reproducibility fundamentals

- (e.g., "Always pin the upstream commit before cloning; `main` drift caused 2 weeks of mis-aligned numbers in the 2024-Q3 project.")
  *Citation: paper-repro/2024-Q3/s3dis-7*

### 2.2 Data hygiene

- (e.g., "Compute dataset MD5 once and store it in `data_contract.md`; do not rely on file count alone.")
  *Citation: ...*

### 2.3 Compute & scheduling

- (e.g., "Reserve 2× expected GPU-hours; long-tail variance is the norm, not the exception.")
  *Citation: ...*

### 2.4 Tooling

- (e.g., "`training_monitor.py` STALLED rule fires 30 s after GPU util drops below 5%; tune for your hardware.")
  *Citation: ...*

### 2.5 Human-in-the-loop

- (e.g., "If a human is asked for approval twice in 24 h, escalate — you're probably missing context.")
  *Citation: ...*

---

## Update protocol

| Action | Where to write | Who |
|---|---|---|
| Add a decision summary | §1.1 | auto-mirror from DECISION_LOG.md |
| Log a trap or lesson | §1.2 / §1.4 | agent or human |
| Promote a lesson to global | §2.* | human (after ≥ 1 cross-project validation) |
| Update project facts | §1.5 | auto (or agent when facts change) |

Edits to §2 must include a citation to the originating project.

---

## 3. GitHub Absorption State Machine (P11_T01)

When `repro-lead` ingests lessons from external GitHub projects (via
`/repro-crawl` and topic-graph audits), each candidate flows through a
**7-state lifecycle** before it can be promoted into §2 (Global
Knowledge).

### 3.1 Seven states

```
candidate → quarantined → audited → extracted → tested → approved → released
   │           │           │          │          │          │          │
   │           │           │          │          │          │          └─ 6: published in §2
   │           │           │          │          │          └─ 5: human-approved
   │           │           │          │          └─ 4: regression tests pass
   │           │           │          └─ 3: lesson drafted, ready to test
   │           │           └─ 2: safety + license + relevance reviewed
   │           └─ 1: copied to scratch dir, no side-effects
   └─ 0: identified via search / topic-graph
```

A candidate can be **Rejected** from any state with a recorded reason.

### 3.2 Four extraction categories

Each `extracted` lesson is tagged with exactly one category:

| Category | Definition | Example |
|---|---|---|
| **workflow** | a procedure or step-ordering that improved outcomes | "Pre-fill `research_contract.md` from `repro_spec.yaml` before any clone" |
| **knowledge** | a domain fact that the agent should remember | "S3DIS Area-6 mIoU degrades ≥0.5 pp when `ignore_label=0` is removed" |
| **tooling** | a tool, library, or script worth keeping | "`scripts/training_monitor.py` STALLED rule fires 30 s after GPU util drops" |
| **trap** | a pitfall to avoid | "Don't auto-tune batch size during M4; it masked a real optimizer bug" |

### 3.3 Five output files (per absorption round)

Every `/repro-evolution` round writes:

1. `evolution_proposal.md` — diff between current §2 and proposed §2
2. `evolution_regression_report.md` — results of `tests/test_regression.py`
3. `evolution_audit.json` — per-candidate audit (license, relevance, safety)
4. `evolution_lessons.jsonl` — appended `extracted` lessons
5. `evolution_failures.jsonl` — appended rejections with reasons

These 5 files live under `output/evolution/` and are required for any
human-approval decision.