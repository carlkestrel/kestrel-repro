# Third-Party Code and License Audit

**Project**: kestrel-repro (dl-paper-repro)  
**Date**: 2026-07-17  
**Auditor**: Third-Party Code Audit

---

## 1. License Files Found

| File | License | Coverage |
|------|---------|----------|
| `/LICENSE` | MIT License | Entire project |

**Status**: Project is covered by MIT License.

---

## 2. Source Code License Headers

**Findings**: No license headers were found in individual source files.

**Assessment**: This is acceptable because:
- The project has a top-level MIT LICENSE file
- All code is original or appropriately attributed
- No third-party code was directly copied

---

## 3. Third-Party Code Analysis

### 3.1 NORA Reference (Architectural Inspiration)

| Field | Value |
|-------|-------|
| source_project | NORA (Night Owl Research Agent) |
| source_url | https://github.com/GRIND-Lab-Core/night_owl_research_agent |
| license | MIT License |
| copied_or_adapted | Architecture-inspired, code NOT copied |
| local_path | N/A - no direct copies |
| recommended_action | None required |

**Analysis**:
- The `NORA_ADAPTATION_NOTES.md` documents the architectural mapping between NORA concepts and this project's implementations
- All NORA-inspired components were re-implemented from scratch
- NORA is MIT-licensed, same as this project
- No direct code copying occurred

**NORA-Inspired Components**:
- `scripts/orchestrator/agents/base.py` - Specialist Agent architecture
- `scripts/orchestrator/review_loop.py` - Auto-review loop pattern
- `scripts/orchestrator/approval_gate.py` - Approval gate mechanism
- `scripts/orchestrator/policy_engine.py` - Policy engine with AUTO_PROCEED
- `scripts/ostar/` - OSTAR module for soak testing
- `scripts/research_crawler.py` - NORA-style paper search

### 3.2 Fixtures Directory (Test Code)

| Field | Value |
|-------|-------|
| source_project | N/A - Synthetic test code |
| source_url | N/A |
| license | N/A (original test fixtures) |
| copied_or_adapted | Original |
| local_path | `fixtures/` |
| recommended_action | None required |

**Analysis**: All fixtures are synthetic test code created specifically for testing the reproduction pipeline:

| Fixture | Purpose |
|---------|---------|
| `fixtures/golden_torch_A/` | Tiny PyTorch training for golden tests |
| `fixtures/golden_pointcloud_B/` | Simple PointNet for classification tests |
| `fixtures/minimal_pytorch_repo/` | Minimal PyTorch with numpy fallback |

None of these are copies of external projects. They are minimal implementations for testing purposes only.

### 3.3 scripts/ostar/ Module

| Field | Value |
|-------|-------|
| source_project | N/A - Original implementation |
| source_url | N/A |
| license | N/A (original code) |
| copied_or_adapted | Original |
| local_path | `scripts/ostar/` |
| recommended_action | None required |

**Analysis**: OSTAR (Overnight Soak Test and Repair) is an original module for long-running soak tests with auto-repair capabilities. Not based on any external project.

### 3.4 Research Crawler

| Field | Value |
|-------|-------|
| source_project | N/A - Original implementation |
| source_url | N/A |
| license | N/A (original code) |
| copied_or_adapted | Original |
| local_path | `scripts/research_crawler.py` |
| recommended_action | None required |

**Analysis**: Original implementation with NORA-style enhancements for paper search and web crawling. Not copied from external sources.

### 3.5 External API Dependencies

| API | Usage | License Consideration |
|-----|-------|---------------------|
| GitHub API | `scripts/orchestrator/agents/github_code_search.py` | Public API, requires rate limit compliance |
| ArXiv API | `scripts/research_crawler.py` | Public API |
| Semantic Scholar API | `scripts/research_crawler.py` | Public API |

**Assessment**: These are public APIs used via standard HTTP requests. No SDK code was copied.

### 3.6 Rule Files

| File | Purpose |
|------|---------|
| `rules/crawler-input-safety.mdc` | Safety constraints for web crawler |
| `rules/reproduction-gates.mdc` | Reproduction workflow gates |

**Analysis**: Original safety rules, not copied from external sources.

---

## 4. No Third-Party Code Copies Found

After thorough analysis, **no direct code copies from external projects were identified**. All code in this repository is either:

1. **Original implementation** - Created specifically for this project
2. **Architecture-inspired** - NORA concepts re-implemented from scratch
3. **Synthetic test fixtures** - Created for testing purposes only

---

## 5. Dependency Analysis

### 5.1 Standard Library (No External Dependencies)

The project uses only Python standard library modules:
- `argparse`, `json`, `os`, `sys`, `pathlib`, `subprocess`
- `sqlite3`, `hashlib`, `re`, `time`, `datetime`
- `typing`, `dataclasses`, `abc`

### 5.2 Optional Dependencies

| Package | Usage | Required |
|---------|-------|----------|
| `yaml` | Configuration file parsing | Optional (graceful fallback) |
| `pytest` | Test runner | Development only |
| `torch` | Deep learning framework | Optional (fixture has fallback) |

---

## 6. License Compatibility

| Component | License | Compatible with MIT? |
|-----------|---------|-------------------|
| Project code | MIT | Yes |
| NORA inspiration | MIT | Yes |
| Standard library | PSF | Yes |
| PyTorch | BSD | Yes |
| PyYAML | MIT | Yes |

**Overall**: Project is fully MIT-licensed with no license conflicts.

---

## 7. THIRD_PARTY_NOTICES.md Section

**Recommendation**: A THIRD_PARTY_NOTICES.md section is NOT required because:

1. No third-party code was copied or adapted
2. All code is original or architecture-inspired with re-implementation
3. No external dependencies require attribution
4. NORA reference is MIT-licensed (same as this project)

---

## 8. Summary and Recommendations

| Item | Status | Action Required |
|------|--------|-----------------|
| LICENSE file | OK | None |
| License headers in code | OK (project-level LICENSE) | None |
| NORA code copies | None found | None |
| Third-party code | None found | None |
| External dependencies | Standard library + optional | None |
| THIRD_PARTY_NOTICES.md | Not required | None |

### LICENSE_DECISION_REQUIRED: No

All code in this repository is either:
- Original implementation under MIT license
- Architecture inspiration from NORA (MIT) with full re-implementation
- Synthetic test fixtures for testing purposes

No third-party code requires additional attribution or license notices.

---

## 9. Appendix: Code Attribution Notes

The following files contain NORA-style comments but implement original code:

| File | NORA Reference | Implementation |
|------|---------------|----------------|
| `scripts/orchestrator/agents/base.py` | Concept inspiration | Original |
| `scripts/orchestrator/review_loop.py` | Concept inspiration | Original |
| `scripts/orchestrator/approval_gate.py` | Concept inspiration | Original |
| `scripts/orchestrator/policy_engine.py` | Concept inspiration | Original |
| `scripts/ostar/*.py` | New module | Original |
| `scripts/research_crawler.py` | Concept inspiration | Original |

---

*Audit completed: 2026-07-17*
