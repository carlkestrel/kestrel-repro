# Documentation Completeness Analysis: kestrel-repro

**Date**: 2026-07-17
**Target**: `/home/carlkestrel/.cursor/plugins/local/kestrel-repro`
**Analyst**: Documentation Audit

---

## Summary

The repository has a solid README (256 lines) and good supplementary docs, but lacks 6 of 8 standard GitHub documentation files. The main README covers ~14 of 20 key requirements but has critical gaps: no citation method, no config examples, no test instructions, and no clear relationship to NORA/AI-Researcher/SiamKPConv despite the design notes existing internally.

---

## Part I: File Presence Audit

### Top-Level Documentation Files

| File | Status | Notes |
|------|--------|-------|
| `README.md` | **EXISTS** | 256 lines, primary entry point |
| `README_zh-CN.md` | **MISSING** | No Chinese translation |
| `CONTRIBUTING.md` | **MISSING** | Referenced in README line 252 but does not exist |
| `SECURITY.md` | **MISSING** | Only `docs/security.md` (Chinese, not top-level) |
| `LICENSE` | **EXISTS** | MIT License, Copyright (c) 2026 Research Automation |
| `CITATION.cff` | **MISSING** | No citation file |
| `CHANGELOG.md` | **EXISTS** | 79 lines, detailed v0.1.0 release notes |
| `THIRD_PARTY_NOTICES.md` | **RECOMMENDED** | Should exist; third-party dependencies are used (PyTorch, various packages) |

### Recommendation

1. **Create `CONTRIBUTING.md`** — one sentence in the README line 252 ("Contributions welcome! Please see CONTRIBUTING.md for guidelines.") references a non-existent file. Must be created.
2. **Create `SECURITY.md`** — move or adapt `docs/security.md` (currently Chinese) to top-level. Add a standard security policy.
3. **Create `CITATION.cff`** — researchers need a standardized citation file.
4. **Create `README_zh-CN.md`** — the `docs/security.md` is in Chinese; if internationalization is intended, a full `README_zh-CN.md` is expected.
5. **Consider `THIRD_PARTY_NOTICES.md`** — relevant if distributing bundled dependencies.

---

## Part II: README Completeness Against 20 Requirements

### Requirements Checklist

| # | Requirement | Status | Assessment |
|---|-------------|--------|------------|
| 1 | Project positioning | **PARTIAL** | Lines 1-5 state "plugin for Cursor" and "evidence-driven", but does not clearly explain the competitive differentiation vs. existing tools. |
| 2 | NOT a copy of NORA/AI-Researcher/SiamKPConv | **MISSING** | Only found in `NORA_ADAPTATION_NOTES.md` (internal design doc), not in README. |
| 3 | What workflow ideas were borrowed | **MISSING** | Same as #2 — NORA_ADAPTATION_NOTES.md has this, but README says nothing about intellectual lineage. |
| 4 | Core features | **PRESENT** | Lines 14-24 list 9 features. Good coverage. |
| 5 | Current maturity | **MISSING** | No "maturity", "alpha", "beta", or "stable" designation. CHANGELOG shows v0.1.0 but this is not referenced. |
| 6 | Training modes supported | **PRESENT** | Lines 153-159 have a table of 3 modes (strict_repro, optimized_repro_safe, experimental_fast). Clear. |
| 7 | Installation method | **PRESENT** | Lines 29-38 cover git clone and Cursor reload. Adequate. |
| 8 | Cursor usage | **PARTIAL** | Lines 41-46 show a one-liner `/repro-init` example. No explanation of how the plugin integrates with Cursor agent, what slash commands are available, or how to invoke them. |
| 9 | CLI quick start | **PRESENT** | Lines 26-75 provide a 5-step workflow. Lines 140-151 cover `reproctl.py` commands. |
| 10 | Takeover method | **MISSING** | `docs/takeover_workflow.md` exists (203 lines, Chinese) but is not mentioned or linked from README. |
| 11 | Smoke test method | **PARTIAL** | Lines 196-200 describe L0-L3 in the workflow. No standalone test commands or expected outputs. |
| 12 | Fast vs Strict difference | **PRESENT** | Lines 155-159 table shows the distinction. |
| 13 | Metric evidence chain | **PARTIAL** | Lines 8-9 and 22-23 mention "evidence chain" but never explains what fields are required (commit, config, data manifest, seed, command, checkpoint, raw metrics). No concrete example. |
| 14 | Data/model distribution note | **MISSING** | No note about how data and models are distributed or accessed (e.g., S3DIS requires registration, weights hosted on Google Drive). |
| 15 | Config examples | **MISSING** | No example of `repro_spec.yaml`, `repo_adapter.yaml`, or `sources.lock.yaml`. |
| 16 | Test method | **MISSING** | No section on how to run the plugin's own test suite. No `pytest` invocation, no test targets. |
| 17 | Known limitations | **PRESENT** | Lines 230-240 list 5 limitations. Good. |
| 18 | Security notes | **PARTIAL** | `docs/security.md` exists but is Chinese and not linked from README. The README has no security section at all. |
| 19 | Citation method | **MISSING** | No `CITATION.cff`, no citation text in README. |
| 20 | Third-party acknowledgments | **MISSING** | No THIRD_PARTY_NOTICES.md. No inline acknowledgments in README. |

### Score: 9/20 Fully Addressed, 4/20 Partial, 7/20 Missing

---

## Part III: Detailed Gap Analysis with Recommendations

### GAP 1: Project Positioning and Differentiation (Requirements 1, 2, 3)

**Problem**: The README positions kestrel-repro as "evidence-driven deep learning paper reproduction" but never explains:
- What it is NOT (not a copy of NORA, AI-Researcher, SiamKPConv)
- Where its ideas come from (NORA's evidence discipline, but re-architected)
- How it differs from simpler approaches (e.g., running the original training script with the same hyperparameters)

**Recommendation**: Add a "How This Compares" section to README:

```markdown
## How This Compares

**kestrel-repro is not a copy of:**
- **NORA** — We drew inspiration from NORA's evidence-first philosophy and generator/evaluator separation, but re-architected everything using SQLite-based state, Python-based orchestration, and Cursor plugin conventions instead of Claude Code prompt files.
- **AI-Researcher** — This plugin focuses exclusively on reproducing existing papers, not generating new research.
- **SiamKPConv** — We are repository-agnostic. KPConv is just one example paper we can reproduce.

**What makes us different:**
- Staged gate enforcement that programmatically blocks training until evidence gates pass
- Hardware-fit assessment before cloning
- 4-level short-loop validation (L0–L3) before any full training
- Evidence chain completeness verification for every reported metric
```

---

### GAP 2: Maturity Level (Requirement 5)

**Problem**: No indication of project maturity. A user cannot tell if this is experimental, alpha, or production-ready.

**Recommendation**: Add a badge or status line near the top of README:

```markdown
## Status

**Version**: 0.1.0 (alpha)
**Pipeline stages**: 0/4 implemented (documentation, core workflow, evidence verification, paper writing)
**Known limitations**: See [Limitations](#limitations)
```

---

### GAP 3: Cursor Usage Guide (Requirement 8)

**Problem**: Only one `/repro-init` example. No explanation of:
- How to invoke slash commands in Cursor Agent
- What slash commands are available
- How the plugin's agents and skills integrate

**Recommendation**: Expand the "Quick Start" section with a Cursor-specific subsection:

```markdown
### Using with Cursor Agent

Once the plugin is installed, the following slash commands become available:

| Command | Purpose |
|---------|---------|
| `/repro-init` | Initialize a new reproduction project |
| `/repro-discover` | Find and rank candidate GitHub repositories |
| `/repro-acquire` | Safely clone a repository |
| `/repro-fit-hardware` | Assess hardware compatibility |
| `/repro-audit` | Audit paper, source, data, and metrics |
| `/repro-preflight` | Run environment and dataset checks |
| `/repro-short-loop` | Run L0–L3 smoke tests |
| `/repro-benchmark` | Profile throughput and parity |
| `/repro-launch` | Start full training (gate-enforced) |
| `/repro-verify` | Verify evidence chain |
| `/repro-decision` | Generate GO/PIVOT/NO-GO report |

To use: Open Cursor Agent and type any command (e.g., `/repro-init paper=https://arxiv.org/abs/...`).
```

---

### GAP 4: Takeover Method (Requirement 10)

**Problem**: `docs/takeover_workflow.md` (203 lines) exists but is completely invisible from README.

**Recommendation**: Add a "Resuming and Takeover" subsection under Quick Start or as its own section:

```markdown
## Resuming an Interrupted Project

See [Takeover Workflow](docs/takeover_workflow.md) for the full guide. Quick summary:

1. Check status: `python scripts/reproctl.py status --project .`
2. Resume: `python scripts/reproctl.py resume --project .`
3. Verify: `python scripts/reproctl.py verify --project .`
```

---

### GAP 5: Smoke Test Method (Requirement 11)

**Problem**: L0-L3 are described in the workflow but no standalone commands are shown for running them individually or interpreting their outputs.

**Recommendation**: Add a dedicated section:

```markdown
## The 4-Level Short Loop

Before any full training, the plugin runs 4 progressively harder checks:

| Level | Name | What It Tests | Pass Criteria |
|-------|------|---------------|---------------|
| L0 | Smoke test | Forward + backward pass on 1 batch | No exceptions |
| L1 | Overfit test | Train on 1 batch to near-zero loss | Loss < 0.01 in 50 steps |
| L2 | Mini loop | Train on 1-10% of data for 1-3 epochs | Loss decreases monotonically |
| L3 | Checkpoint resume | Save and reload checkpoint | Metrics within 1e-5 |

Run individually:
```bash
python scripts/reproctl.py run-short-loop --level L0
python scripts/reproctl.py run-short-loop --level L1 --overfit-steps 50
python scripts/reproctl.py run-short-loop --level L2 --epochs 3
python scripts/reproctl.py run-short-loop --level L3
```
```

---

### GAP 6: Metric Evidence Chain (Requirement 13)

**Problem**: "Evidence chain" is mentioned but never defined. What fields are required? What does completeness mean?

**Recommendation**: Add a section:

```markdown
## Evidence Chain

Every reported metric must be traceable through this chain:

1. **Claim**: The paper's reported value (e.g., "mIoU = 70.3% on S3DIS Area 5")
2. **Commit**: Git SHA of the exact code used (`sources.lock.yaml`)
3. **Config**: Full hyperparameters (`repro_spec.yaml`)
4. **Data manifest**: Dataset version, split, preprocessing (`data_contract.md`)
5. **Seed**: Random seed used for reproducibility
6. **Command**: Exact training command executed
7. **Checkpoint**: Model weights at evaluation time
8. **Raw metrics**: Unevaluated training logs

Use `/repro-verify` to check chain completeness. Use `scripts/artifact_verify.py` for programmatic verification.
```

---

### GAP 7: Data/Model Distribution Note (Requirement 14)

**Problem**: No guidance on dataset access restrictions, model weight distribution, or common pitfalls (e.g., S3DIS requires registration, some weights are on Google Drive).

**Recommendation**: Add a section:

```markdown
## Data and Model Distribution

Reproducing papers requires accessing datasets and model weights, which may be distributed differently:

| Dataset | Access | Notes |
|---------|--------|-------|
| S3DIS | Registration required | https://spatial.stanford.edu/dataset |
| ScanNet | Registration required | https://scannet.cs.cornell.edu |
| SemanticKITTI | Public download | Direct download link |
| Model weights | Varies | Some on GitHub LFS, some on Google Drive, some in `.tar.gz` archives |

The plugin's `data_contract.md` template captures the expected access method for each dataset. See `docs/reproduction_protocol.md` for dataset-specific guidance.
```

---

### GAP 8: Config Examples (Requirement 15)

**Problem**: No example configs shown anywhere in README. The architecture section lists templates but doesn't show their contents.

**Recommendation**: Add an "Example Configs" section or a link to a config examples file:

```markdown
## Example Configs

See the `templates/` directory for full templates:

- `templates/repro_spec.yaml` — Paper metadata, target metrics, mode selection
- `templates/repo_adapter.yaml` — Repository-specific train/test commands
- `templates/sources.lock.yaml` — Pinned repository URLs and commits

Minimal example `repro_spec.yaml`:

```yaml
paper:
  arxiv_url: https://arxiv.org/abs/2103.14641
  title: "KPConv: Flexible and Deformable Convolution for Point Clouds"
  target_metric: "mIoU on S3DIS Area 5"
  reported_value: 70.3

reproduction:
  mode: strict_repro
  seed: 42
  epochs: 300
  hardware_profile: auto  # or explicit: gpu: RTX 3090, ram: 32GB
```
```

---

### GAP 9: Test Method (Requirement 16)

**Problem**: No test instructions for the plugin itself. `docs/testing_and_ci.md` exists (found via glob) but README has no reference.

**Recommendation**: Add a "Testing" section:

```markdown
## Testing

Run the plugin's own test suite:

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires a test repository)
pytest tests/integration/ -v

# Smoke test for reproctl.py
python scripts/reproctl.py doctor --project .

# CLI help validation
python scripts/reproctl.py --help
```

See [Testing and CI](docs/testing_and_ci.md) for full details.
```

---

### GAP 10: Citation Method (Requirement 19)

**Problem**: No citation file or citation text. Researchers cannot cite the tool.

**Recommendation**: Create `CITATION.cff`:

```yaml
cff-version: 1.2.0
message: "If you use this plugin in your research, please cite it."
type: software
title: "kestrel-repro"
version: 0.1.0
date-released: 2026-07-15
url: "https://github.com/kestrel/dl-paper-repro"
authors:
  - name: Research Automation
license: MIT
```

And add citation text to README:

```markdown
## Citation

If you use kestrel-repro in your research, please cite:

```bibtex
@software{kestrel_repro_2026,
  title = {kestrel-repro: Evidence-driven Deep Learning Paper Reproduction Plugin for Cursor},
  author = {Research Automation},
  year = {2026},
  url = {https://github.com/kestrel/dl-paper-repro},
  version = {0.1.0}
}
```
```

---

### GAP 11: Security Notes (Requirement 18)

**Problem**: `docs/security.md` exists but is in Chinese and not linked from README. A top-level `SECURITY.md` is missing entirely.

**Recommendation**: Create `SECURITY.md` (English, GitHub standard location):

```markdown
# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

Do NOT open a public issue for security vulnerabilities.

Email: security@example.com
Subject: [kestrel-repro Security] <brief description>

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We aim to respond within 48 hours and patch within 2 weeks.

## Security Design

- **Safe cloning**: Static security audit runs before any installation script executes
- **No curl | bash**: The plugin never executes remote installation scripts
- **Credential management**: API tokens must be set via environment variables, never hardcoded
- **Secrets redaction**: `scripts/startup/secrets_redactor.py` redacts Bearer tokens, passwords, and API keys from logs
```

---

## Part IV: Additional Observations

### Supplementary Documentation Quality

The `docs/` directory contains substantial, well-structured documentation:

| File | Language | Quality |
|------|----------|---------|
| `docs/quickstart.md` | Chinese | Good, covers CLI extensively |
| `docs/takeover_workflow.md` | Chinese | Good, 7-phase workflow |
| `docs/faq.md` | Chinese | Comprehensive Q&A |
| `docs/security.md` | Chinese | Detailed security policy |
| `docs/roadmap.md` | Mixed | Clear version roadmap |
| `docs/architecture.md` | Unknown | Needs review |
| `docs/testing_and_ci.md` | Unknown | Needs review |

**Issue**: Most supplementary docs are in Chinese, which may limit contribution and adoption by non-Chinese speakers. If internationalization is intended, English versions should be prioritized. If the project is China-focused, a `README_zh-CN.md` should exist at the top level.

### NORA Adaptation Notes (`NORA_ADAPTATION_NOTES.md`)

This file (103 lines) is excellent for internal design documentation but contains information that belongs in the public README (#2, #3 above). Specifically:
- Table mapping NORA concepts to kestrel-repro equivalents (lines 10-22)
- List of NORA problems avoided (lines 34-43)
- List of NORA ideas borrowed and reimplemented (lines 45-78)

### Architecture Section

The README architecture diagram (lines 81-127) is useful but shows an outdated directory structure. The actual directory uses `scripts/` for Python tooling, not `src/`. The architecture section should be regenerated from actual file listings.

### CHANGELOG

Well-maintained (79 lines). Clear v0.1.0 release notes with plugin structure, agents, skills, rules, commands, scripts, templates, and design decisions. Good example to follow.

---

## Part V: Priority Recommendations

### Must Fix (Before Public Release)

1. **Create `CONTRIBUTING.md`** — referenced in README but does not exist.
2. **Create `SECURITY.md`** — GitHub best practice; move English content from `docs/security.md`.
3. **Create `CITATION.cff`** — researchers need standardized citation.
4. **Add sections for Requirements 2, 3** — explicitly state "not a copy of NORA" and explain intellectual lineage. Either move content from `NORA_ADAPTATION_NOTES.md` or summarize in README.
5. **Add config examples** — one concrete `repro_spec.yaml` example would dramatically help adoption.
6. **Add test instructions** — `tests/` directory exists but README has no test documentation.
7. **Link supplementary docs** — README should reference `docs/quickstart.md`, `docs/takeover_workflow.md`, `docs/security.md`, `docs/faq.md`, `docs/testing_and_ci.md`.

### Should Fix (Before v1.0)

8. **Add maturity indicator** — version badge, "alpha/beta/stable" designation.
9. **Create `README_zh-CN.md`** — if international audience is intended.
10. **Expand Cursor usage guide** — list all slash commands with descriptions.
11. **Add data/model distribution note** — dataset access restrictions are a common pitfall.
12. **Add citation text to README** — bibtex and plain-text citation alongside `CITATION.cff`.

### Nice to Have

13. **Create `THIRD_PARTY_NOTICES.md`** — for compliance with bundled dependencies.
14. **Expand smoke test documentation** — expected outputs, pass criteria, troubleshooting.
15. **Fix architecture diagram** — regenerate from actual directory structure.
16. **Add evidence chain section** — concrete example of the 8-field evidence chain.

---

*End of analysis*
