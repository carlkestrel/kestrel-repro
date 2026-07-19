# Kestrel-Repro R3R Task Ledger

**最后更新**: 2026-07-19 18:04 (Asia/Shanghai)
**当前阶段**: R3-CONTINUATION（修复 3 个 chaos test fail）
**模式**: worktree_fallback（单 Lead agent 串行推进）

---

## Baseline 验证 (2026-07-19)

| 指标 | refactor_state.json (旧) | 当前实测 | 差异 |
|---|---|---|---|
| collected | 258 | **301** | +43 (新增测试) |
| passed | 237 | **298** | +61 (新 + 之前 fail 现 pass) |
| failed | 21 | **3** | −18 (其中 test_chaos.py 7→3, test_orchestrator.py 14→0) |
| exit_code | 1 | 1 | 仍 failed |

**关键事实**：
- refactor_state.json 是 **stale snapshot**（已过期）
- 真实 baseline：**301 collected / 298 pass / 3 fail**（全在 test_chaos.py）
- junit XML: `ci_reports/R3_BASELINE_2026-07-19.xml` (32523 bytes, 41.67s)
- 必须 PYTHONPATH=`kestrel-repro:kestrel-repro/scripts` 才能跑（scripts 是 namespace package）

**3 个 fail**：
1. `TestTrainingSubprocessKilled::test_training_killed_preserves_checkpoint` — schema PASSED vs PASS
2. `TestGpuUnavailable::test_gpu_unavailable_graceful_degradation` — exit 7 vs (0, 1)
3. `TestAutoRetryHitsLimit::test_max_retries_then_fail` — attempts 0 vs ≥2

---

## Active Tasks（进行中）

### W0 — 收尾
- [x] W0-1 读真实基线
- [x] W0-2 重定位状态文件 + commit + push
- [x] W0-3 重写状态文件
- [x] **W0-4 baseline pytest 验证（301/298/3）**

---

## Backlog（按 wave 排序）

### Wave 1 — test_chaos.py 收尾（修 3 个 fail）
- [ ] W1-1 修 CHAOS-LIVE-1: status PASSED → PASS 的一致性 — `test_training_killed_preserves_checkpoint`
- [ ] W1-2 修 CHAOS-LIVE-2: GPU unavailable exit code 7 → (0, 1) — `test_gpu_unavailable_graceful_degradation`
- [ ] W1-3 修 CHAOS-LIVE-3: retry counter 不增 — `test_max_retries_then_fail`

**预期**: 301 collected / **301 pass / 0 fail** / exit_code 0

### Wave 2 — 新增功能
- [ ] W2-1 R3-6 GPU resource lock 实现
- [ ] W2-2 R3-7 Shell command safety boundary（需用户审批）

---

## 待决策

### P-2026-07-19-C: CHAOS-LIVE-1 怎么修？
- **选项 A**: 改 controller 写 'PASS'（test 不变）
- **选项 B**: 改 test 接受 'PASSED'（canonical schema）

**Recommend**: B — 因为 'PASSED' 是 refactor_state 提到的 canonical schema 名，不应回退到 'PASS'。

### P-2026-07-19-D: CHAOS-LIVE-2 怎么修？
- **选项 A**: 改 subprocess 让 GPU 缺失时返回 exit 0/1（graceful）
- **选项 B**: 改 test 接受 exit 7（BLOCKED 也是合理响应）

**Recommend**: A — AUTOMATION_ARCHITECTURE.md §8.1 "GPU 训练" 是 REQUIRE_APPROVAL，BLOCKED 应该是显式 user-facing 信号；test 期望 graceful 说明原意是优雅降级。但需要确认是否与现有 gate 行为冲突。

### P-2026-07-19-E: CHAOS-LIVE-3 怎么修？
- **选项 A**: 修 controller retry counter
- **选项 B**: 修 test fixture

**Recommend**: 需要先看 test fixture — 大概率是 fixture 没正确模拟 retry 路径。

---

## Done（完成）

- [x] 状态文件迁移到 kestrel-repro/.r3r-state/ + commit 43440ce + push origin
- [x] PROJECT_CHARTER.md + ORCHESTRATION_STATE.json + HANDOFF.md 重写基于真实基线
- [x] baseline pytest 验证完成（301/298/3）
- [x] ci_reports/R3_BASELINE_2026-07-19.xml 落地（32523 bytes）

---

## Test Progress Timeline

| 时间 | collected | passed | failed | exit | source |
|---|---|---|---|---|---|
| refactor_state.json (旧) | 258 | 237 | 21 | 1 | 旧 snapshot |
| 2026-07-19 18:04 | **301** | **298** | **3** | 1 | pytest 当前跑 |
| W1 完成后（目标） | 301 | 301 | 0 | 0 | pytest |