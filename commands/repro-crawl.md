---
description: Run the constrained research crawler from scripts/research_crawler.py with the safety rule from rules/crawler-input-safety.mdc.
---

# /repro-crawl

> Bounded web crawl with explicit domain whitelist + per-host rate limit
> + robots.txt respect + 5 safety constraints (rules/crawler-input-safety.mdc).

## Usage

```
/repro-crawl --urls https://arxiv.org/abs/2401.12345 ...   # one-shot
/repro-crawl --plan templates/search_plan.json --urls ...  # explicit plan
/repro-crawl --depth 1                                    # allow 1 link hop
/repro-crawl help
```

## What this command does

1. Reads `rules/crawler-input-safety.mdc` (always-on).
2. Loads `templates/search_plan.json` (or `.yaml`) for whitelist, rate
   limits, and runtime caps.
3. Constructs a `scripts/research_crawler.py:ResearchCrawler` instance.
4. Calls `crawler.fetch(urls, max_depth=...)`.
5. Writes raw responses to `raw_crawl_data/<sha256[:16]>.bin` + ETag cache.
6. Validates extracted facts before any `templates/topic_graph.json` write.

## Pre-conditions

- `templates/search_plan.json` (or `.yaml`) exists.
- `ALLOW_NETWORK=true` (default). If false, refuse and tell the user
  to set the flag via a `risk_override` decision row.
- `rules/crawler-input-safety.mdc` is loaded (auto-loaded by Cursor).

## Output

```
[repro-crawl] loading plan ............................... OK
[repro-crawl] safety rules applied ....................... 5/5
[repro-crawl] fetching 3 URLs ............................ ok=2, out_of_whitelist=1
[repro-crawl] raw_crawl_data/ written .................... 2 files (1.2 MB)
[repro-crawl] facts extracted ............................ 14 (validated against 2 backends each)
[repro-crawl] decision = D__ → DECISION_LOG.md
```

## Failure modes

- URL not in whitelist → `out_of_whitelist`, recorded in crawl log, no
  body fetched.
- robots.txt blocks → `blocked_by_robots`, no fetch.
- Response > 5 MB → `too_large`, truncated to 5 MB.
- Timeout / network error → exponential backoff up to `retry_max` (3).
- Extracted fact can't be cross-validated → fact is **not** written to
  `topic_graph.json`; warning logged.

## Implementation

`scripts/reproctl.py crawl --urls ... [--plan PATH] [--depth N]`.