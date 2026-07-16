# Failure Case Report

> Structured record of every failure encountered during the
> reproduction, with a four-column "现象→影响→修复→证据" structure.

## Top overview (总览)

| Category | Count |
|---|---|
| 已修复 (Fixed) |  |
| 已规避 (Worked around) |  |
| 未验证 (Unverified) |  |
| **Total** |  |
| **source:** | (this file) |

---

## §1  Fixed failures (已修复)

| ID | 现象 (Symptom) | 影响 (Impact) | 修复 (Fix) | 证据 (Evidence) |
|---|---|---|---|---|
| F001 |  |  |  |  |
| F002 |  |  |  |  |
| ... |  |  |  |  |

## §2  Worked-around failures (已规避)

| ID | 现象 | 影响 | 规避方法 | 证据 |
|---|---|---|---|---|
| W001 |  |  |  |  |
| ... |  |  |  |  |

## §3  Unverified failures (未验证)

| ID | 现象 | 影响 | 当前状态 | 风险 |
|---|---|---|---|---|
| U001 |  |  |  |  |
| ... |  |  |  |  |

---

## §4  Overall retrospective (总体复盘)

- Most common failure category
- Root-cause distribution (data / code / hardware / config)
- Mean time-to-repair per failure
- Lessons learned (→ §1.4 of `templates/project_memory.md`)
- **source:** (this file §1+§2+§3)

---

## Appendix A — Failure timeline

```
2026-07-10 14:32 — F001 raised; root-cause: cuDNN nondeterminism
2026-07-10 15:10 — F001 fix applied; verified by re-run
2026-07-11 09:01 — W001 raised; working around by lowering batch size
```

## Appendix B — Symptom clustering

- Most frequent symptom text (with regex)
- File paths most often involved

## Appendix C — Fix verification protocol

- How each fix was verified (re-run + diff vs. expected)
- Tolerance used

## Appendix D — Cross-reference

- `templates/project_memory.md` §1.2 (Traps hit)
- `templates/project_memory.md` §1.4 (What didn't work)
- `templates/narrative_report.md` §7 (Failures)

## Appendix E — Failure prevention checklist (for next project)

- [ ] (e.g., "Always pin cuDNN version before installing PyTorch")
- [ ] (e.g., "Smoke-test determinism before launching full training")