---
description: Per-item verification of papers / repos / datasets from templates/topic_graph.json.
---

# /geoai-audit

> Verifies every Tier-A/B/C entry in `templates/topic_graph.json` against
> the actual source. 8 verification items per entry.

## Usage

```
/geoai-audit                              # all Tier-A and Tier-B entries
/geoai-audit --tier A                     # restrict to Tier-A only
/geoai-audit --direction weakly_supervised_pointcloud
/geoai-audit --entry <id>                 # single entry
/geoai-audit help
```

## 8 verification items

| # | Item | Pass criterion |
|---|---|---|
| 1 | **Link liveness** | The URL returns HTTP 200 (or a working redirect). |
| 2 | **Hash integrity** | If a sha256 / md5 is provided, it matches the resource. |
| 3 | **Tag presence** | The paper / repo / dataset has the expected tags (e.g., `point-cloud`, `change-detection`). |
| 4 | **Class distribution** | For datasets: per-class point counts match the documented distribution within 5%. |
| 5 | **Protocol match** | For papers: the documented training protocol matches `data_contract.md` §Evaluation. |
| 6 | **License** | License permits reproduction & derivative use. |
| 7 | **Hardware requirements** | The repo's stated VRAM matches `hardware_fit_report.md`. |
| 8 | **Status update** | `REVIEW_STATE.json.open_actions` reflects any open issue. |

## Output

```
[geoai-audit] entries to verify (Tier A+B) .......... 47
[geoai-audit] pass .................................. 41/47
[geoai-audit] fail .................................. 6/47
[geoai-audit] failed entries:
  - weakly_supervised_pointcloud / paper "X" / item 3: missing tag
  - point_cloud_change_detection / repo "Y" / item 6: GPL-3.0 — derivative forbidden
[geoai-audit] decision = D__ → DECISION_LOG.md
```

## Pre-conditions

- `templates/topic_graph.json` exists and has at least 1 entry.
- Network access (`ALLOW_NETWORK=true`) for live link checks.
- The verify list is runnable from any cwd (paths in `topic_graph.json`
  are resolved against the repo root).

## Failure modes

- A Tier-A entry fails any of items 1–7 → mark the entry as
  `verified: false` in `topic_graph.json` and write a `note` row to
  `DECISION_LOG.md`.
- An entry fails item 8 only (status update missing) → it is *not*
  blocking; record it as a `minor` action.

## Implementation

`scripts/reproctl.py geoai-audit [--tier T] [--direction D] [--entry ID]`.