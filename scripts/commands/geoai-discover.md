---
description: Run a 9-dimension GeoAI query expansion, search 4 backends, populate templates/topic_graph.json.
---

# /geoai-discover

> Searches ArXiv / SemanticScholar / GitHub / Papers-with-Code using a
> 9-dimension × 4-query-type expansion engine. Populates
> `templates/topic_graph.json` and writes `candidate_repositories.csv` +
> a stub `dataset_registry.md`.

## Usage

```
/geoai-discover                              # full sweep (3 primary directions)
/geoai-discover --direction point_cloud_change_detection
/geoai-discover --direction weakly_supervised_pointcloud
/geoai-discover --direction environmental_spatial_intelligence
/geoai-discover --depth quick                # ≤50 queries per direction
/geoai-discover --depth deep                 # ≤500 queries per direction
/geoai-discover help
```

## 5-step flow

| Step | Reads | Writes | Notes |
|---|---|---|---|
| **1. Pick direction** | `--direction` or all 3 primary | — | 3 primary: `point_cloud_change_detection`, `weakly_supervised_pointcloud`, `environmental_spatial_intelligence` |
| **2. Expand queries** | direction + 9 dimensions (task / sensor / application / dataset / method / supervision / domain-shift / eval / output) | `query_expansion.json` | 4 query types per (dim, value): exact / keyword / boolean / year-filtered |
| **3. Dispatch to 4 backends** | `query_expansion.json` | `query_results/<backend>_<hash>.json` | ArXiv, SemanticScholar, GitHub, Papers-with-Code |
| **4. Tier & dedup** | `query_results/*` | `candidate_repositories.csv` | A/B/C/D/E scoring per direction |
| **5. Update topic_graph** | `candidate_repositories.csv` + `dataset_registry.md` | `templates/topic_graph.json` | adds to `sub_topics[].papers/datasets/repos`, updates `tier_counts` |

## Pre-conditions

- `templates/topic_graph.json` exists (or is created from the schema example).
- Network access is allowed (controlled by `ALLOW_NETWORK` flag in
  `templates/control_flags.md`; if `false`, abort).
- No concurrent `/geoai-discover` running (state lock via
  `.repro/discover.lock`).

## Output

```
[geoai-discover] step 1/5 pick direction ................... point_cloud_change_detection
[geoai-discover] step 2/5 expand queries ................... 234 queries (9 dims × 6 values × 4 types + head/tail)
[geoai-discover] step 3/5 dispatch ........................ arxiv=234, ss=234, github=234, pwc=234
[geoai-discover] step 4/5 tier & dedup ..................... 412 candidates (A=12, B=37, C=104, D=259, E=0)
[geoai-discover] step 5/5 update topic_graph ............... OK (3 directions, 7 sub-topics)
[geoai-discover] decision = D__ → DECISION_LOG.md
```

## Failure modes

- `ALLOW_NETWORK=false` → refuse; the user must toggle the flag with
  a `risk_override` decision row.
- Backend timeout (>30 s per query) → log warning, skip that query,
  continue with the others.
- Empty result set → mark `tier_counts.E++` for "no candidate" and
  continue; never silently pass.

## Implementation

`scripts/reproctl.py geoai-discover [--direction D] [--depth LEVEL]`
calls the 4-backend clients (ArXiv API, SemanticScholar Graph,
GitHub Search API, PWC scraper) and the local query-expansion engine.