# Research Contract

> **Why this file exists**: A reproduction is a *contract* between a paper's
> claims, a code repository, a dataset, a metric, a compute budget, and a
> human. If any of those five things drifts silently, the entire reproduction
> is invalidated. This template makes the contract *explicit* before any
> training run starts.
>
> **Usage**: Fill the placeholders below. Every checkbox must be either
> `[x]` (confirmed by human) or `[ ]` (open / unresolved). All five
> "Allowed / Forbidden" cells are mandatory.

---

## 0. Meta

| Field | Value |
|---|---|
| **Project / Branch** | `dl-paper-repro` |
| **Owner (agent)** | `agent` |
| **Human approver** | |
| **Decision Log row** | `D__` (link `.repro/repro_audit/DECISION_LOG.md`) |
| **Created** | (ISO-8601) |
| **Last updated** | (ISO-8601) |

---

## 1. Paper (the claim source)

| Field | Value |
|---|---|
| **Title** | |
| **Authors** | |
| **Venue / Year** | |
| **arXiv id / DOI** | |
| **Code repo (paper-author)** | |
| **Target table / figure** | |
| **Target metric(s) + paper value** | |
| **Paper hash (sha256 PDF)** | |

`[ ]` Human has confirmed the paper URL + version above.

---

## 2. Code Repository

| Field | Value |
|---|---|
| **Upstream URL** | |
| **Upstream commit (paper-aligned)** | |
| **Local commit after clone** | |
| **License** | |
| **Local path** | `repos/<paper-slug>/` |
| **Adapter path** | `repo_adapter.yaml` |

`[ ]` Upstream commit is pinned (not `main` / `master`).
`[ ]` License permits reproduction & derivative use.
`[ ]` Local clone passes `reproctl check git-pin`.

---

## 3. Goal (the claim to reproduce)

> One sentence. State the *measurable* claim and its tolerance. Do **not**
> write "reproduce the paper" — name the metric, the dataset split, and the
> acceptable gap from the paper value.

**Goal**:

**Pass criterion (quantitative)**: e.g., `mIoU on S3DIS Area-6 ≥ 73.4% (paper 73.9% ± 0.5%)`.

`[ ]` Human has approved the goal above and the pass criterion.

---

## 4. Data

| Field | Value |
|---|---|
| **Dataset name** | |
| **Version / split** | |
| **Source URL / contact** | |
| **License** | |
| **Restricted (application?)** | `[ ] yes  [ ] no` |
| **Expected size (GB)** | |
| **MD5 / SHA256 (if known)** | |
| **Local root** | `${DATA_ROOT}` |

`[ ]` Data is downloadable, or a downloaded snapshot is already on disk.
`[ ]` MD5 / file count matches `data_contract.md`.

---

## 5. Metrics

| Metric | Paper value | Tolerance | Notes |
|---|---|---|---|
| | | | |

`[ ]` Metric definition (per `data_contract.md` §Metric Definition) is identical to paper.
`[ ]` Evaluation protocol (checkpoint selection, voting, TTA) matches paper.

---

## 6. Budget (the cost)

| Resource | Budget |
|---|---|
| **Wall-clock** | e.g., 72 hours |
| **GPU type / count** | |
| **GPU-hours** | |
| **Disk** | |
| **Network egress** | |
| **Deadline** | (ISO-8601) |

`[ ]` Budget is approved by human. Exceeding it requires a new decision row.

---

## 7. Allowed / Forbidden Scope

> Any change outside the `Allowed` list must be recorded as a new decision
> row *before* the change is made. Anything in the `Forbidden` list is
> blocked unless a human explicitly overrides.

### Allowed (no new decision row needed)

- (e.g., "switch CUDA version if `nvcc --version` < 11.7")
- (e.g., "increase batch size up to N if VRAM allows")
- (e.g., "re-run on a second seed from the seed list")

### Forbidden (always requires a new decision row + human sign-off)

- (e.g., "change the loss function")
- (e.g., "replace the backbone")
- (e.g., "use a different dataset split")
- (e.g., "modify evaluation protocol")
- (e.g., "change ignore-label list")

### Out-of-scope (do not attempt unless scope changes)

- (e.g., "hyper-parameter tuning beyond paper-stated values")
- (e.g., "training on additional datasets")

---

## 8. Human Confirmation

> This section is **only** complete when every checkbox in §§1–7 is ticked
> and a human has signed below. Until then the project is in `plan` mode.

`[ ]` All §§1–7 boxes are resolved or explicitly waived.

| Role | Name | Decision | Timestamp |
|---|---|---|---|
| **Human approver** | | `[ ] APPROVE  [ ] REJECT` | |

After human approval, transition to `reproduce` mode (see
`commands/repro-contract.md`) and create a `D__` decision-log row referencing
this file.