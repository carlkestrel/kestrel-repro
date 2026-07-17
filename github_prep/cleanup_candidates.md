# Cleanup Candidates

This document lists files that are candidates for cleanup, organized by recommended action.

## Add to .gitignore

| path | category | reason |
|------|----------|--------|
| .cache/ | CACHE | Crawler cache directory - should not be committed |
| .pytest_cache/ | CACHE | Pytest cache - standard Python test artifact |
| scripts/cvo/__pycache__/ | CACHE | Python bytecode cache for cvo module |
| scripts/ostar/__pycache__/ | CACHE | Python bytecode cache for ostar module |
| tests/__pycache__/ | CACHE | Python bytecode cache for tests |
| **Audit | OBSOLETE | Malformed filename from error output |

## Delete (Safe to Remove)

| path | category | reason |
|------|----------|--------|
| .pytest_cache/ | CACHE | Pytest cache - regenerated on test runs |
| scripts/cvo/__pycache__/ | CACHE | Python bytecode - regenerated on import |
| scripts/ostar/__pycache__/ | CACHE | Python bytecode - regenerated on import |
| tests/__pycache__/ | CACHE | Python bytecode - regenerated on import |
| .cache/crawler/_index.json | CACHE | Crawler index cache - regenerates on crawl |

## Move to Archive

| path | category | reason |
|------|----------|--------|
| .execution/ | LOCAL_RUNTIME | Execution state data - historical runtime data |
| .repro/audit/ | LOCAL_RUNTIME | Audit data - historical audit state |
| .repair/ | LOCAL_RUNTIME | Repair data - bug fixes and rollbacks |
| .stabilization/ | LOCAL_RUNTIME | Stabilization state - process state |
| artifacts/ | LOCAL_RUNTIME | Runtime artifacts - generated during runs |
| performance/ | LOCAL_RUNTIME | Performance data - generated during runs |
| audits/ | OBSOLETE | Old audit reports (v0.1.0, v0.2.0) - superseded |
| ci_reports/ | OBSOLETE | CI reports - historical CI data |
| github_prep/before_*.md | OBSOLETE | Snapshot files from before functionality |
| github_prep/before_tree.txt | OBSOLETE | Tree snapshot |
| github_prep/before_inventory.json | OBSOLETE | Inventory snapshot |
| github_prep/git_status_raw.txt | OBSOLETE | Git status snapshot |
| github_prep/size_info.txt | OBSOLETE | Size information snapshot |

## Local Runtime Data (Do Not Commit)

The following directories contain runtime-generated data and should NOT be committed:

| path | category | reason |
|------|----------|--------|
| .repro/ | LOCAL_RUNTIME | Runtime audit state and logs |
| .execution/ | LOCAL_RUNTIME | Execution state and evidence |
| .repair/ | LOCAL_RUNTIME | Repair state and patches |
| .stabilization/ | LOCAL_RUNTIME | Stabilization state |
| artifacts/ | LOCAL_RUNTIME | Runtime artifacts |
| performance/ | LOCAL_RUNTIME | Performance data |

## Generated Documentation (Regeneratable)

| path | category | reason |
|------|----------|--------|
| docs/html/ | GENERATED | Generated HTML documentation |
| docs/generated/ | GENERATED | Generated documentation files |

## Duplicate Files (Review for Consolidation)

| path | category | reason |
|------|----------|--------|
| docs/html/zh-CN/assets/styles.css | DUPLICATE | Duplicates docs/html/assets/styles.css |
| docs/html/zh-CN/assets/logo.svg | DUPLICATE | Duplicates docs/html/assets/logo.svg |
| docs/html/zh-CN/assets/icons.svg | DUPLICATE | Duplicates docs/html/assets/icons.svg |
| performance/strict_performance.yaml | DUPLICATE | Duplicates template of same name |

## Summary Statistics

| Category | Count | Action |
|----------|-------|--------|
| CACHE | 4 dirs | Delete + Add to .gitignore |
| LOCAL_RUNTIME | 6 dirs + files | Move to archive |
| OBSOLETE | 6 dirs + 1 file | Move to archive or delete |
| GENERATED | 2 dirs | Do not commit (regeneratable) |
| DUPLICATE | 4 files | Review for consolidation |
