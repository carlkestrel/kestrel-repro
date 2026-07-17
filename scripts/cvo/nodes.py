"""
CVO Node Registry — All 30+ validation nodes with their definitions.

Each node defines:
  - node_id, name, version
  - capability_ids (which 13 components it exercises)
  - command / callable
  - timeout_seconds
  - requires_gpu / requires_real_data
  - depends_on (upstream node IDs)
  - input_fields (what it reads)
  - output_fields (what it produces)
  - acceptance criteria (how to judge PASSED/FAILED)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ValidationNode:
    node_id: str
    name: str
    version: str = "0.1.0"
    description: str = ""
    capability_ids: list[str] = field(default_factory=list)
    module: str = ""
    callable: str = ""          # "module.submodule:function" or ""
    timeout_seconds: int = 300
    requires_gpu: bool = False
    requires_real_data: bool = False
    depends_on: list[str] = field(default_factory=list)
    input_fields: list[str] = field(default_factory=list)
    output_fields: list[str] = field(default_factory=list)
    acceptance: str = ""
    notes: str = ""
    retryable: bool = False
    deterministically_fails: bool = False  # True for config/data errors — do not retry


# ── Stage A: Project Discovery ──────────────────────────────────────────────────

VAL_000 = ValidationNode(
    node_id="VAL-000",
    name="BOOTSTRAP",
    version="0.1.0",
    description="Confirm project root, create audit directory, check disk space, "
                "check git status, create audit_id.",
    capability_ids=["CVO"],
    module="cvo.bootstrap",
    callable="cvo.bootstrap:run",
    timeout_seconds=60,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=[],
    input_fields=[],
    output_fields=[
        "audit_manifest.json",
        "audit_id",
        "disk_space_gb",
        "git_commit",
        "git_dirty",
        "plugin_root",
    ],
    acceptance="audit/audit_manifest.json exists; audit_id is non-empty UUID",
)

VAL_010 = ValidationNode(
    node_id="VAL-010",
    name="REPOSITORY_INVENTORY",
    version="0.1.0",
    description="Scan source, config, test, CLI, Cursor, and documentation files. "
                "Generate repository_inventory.json.",
    capability_ids=["CVO"],
    module="cvo.inventory",
    callable="cvo.inventory:run",
    timeout_seconds=300,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-000"],
    input_fields=["audit_manifest.json"],
    output_fields=["repository_inventory.json"],
    acceptance="JSON has keys: python_files, config_files, test_files, cli_files, "
               "cursor_files, total_line_count > 0",
)

VAL_020 = ValidationNode(
    node_id="VAL-020",
    name="ARTIFACT_INVENTORY",
    version="0.1.0",
    description="Scan logs, checkpoints, PLY, CSV, confusion matrix, and HTML report "
                "files. Record path, size, time, hash. Do NOT load large files into GPU.",
    capability_ids=["CVO"],
    module="cvo.artifact_inventory",
    callable="cvo.artifact_inventory:run",
    timeout_seconds=300,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-000"],
    input_fields=["audit_manifest.json"],
    output_fields=["artifact_inventory.json"],
    acceptance="JSON has key 'artifacts' (list), each entry has path, size_bytes, "
               "mtime, sha256 (computed without loading into GPU)",
)


# ── Stage B: Static Functional Audit ──────────────────────────────────────────

VAL_100 = ValidationNode(
    node_id="VAL-100",
    name="PROTOCOL_AUDIT",
    version="0.1.0",
    description="Check paper protocol registration, batch_size=10 locking, "
                "strict vs fast isolation, protocol_diff.md generation.",
    capability_ids=["Protocol Registry", "Training Mode Controller"],
    module="cvo.protocol_audit",
    callable="cvo.protocol_audit:run",
    timeout_seconds=300,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-010"],
    input_fields=["repository_inventory.json"],
    output_fields=["protocol_audit.md", "protocol_diff.md"],
    acceptance="protocol_audit.md exists with sections for: paper registration, "
               "batch_size locking, mode isolation, protocol_diff",
)

VAL_110 = ValidationNode(
    node_id="VAL-110",
    name="DATA_CONTRACT_AUDIT",
    version="0.1.0",
    description="Check PLY element names, x/y/z/label_ch fields, label_ch embedded "
                "vs separate file, pointCloud0/1 requirements, dtype, label range, "
                "class mapping, split, file count and hashes.",
    capability_ids=["Data Contract Auditor"],
    module="cvo.data_contract_audit",
    callable="cvo.data_contract_audit:run",
    timeout_seconds=300,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-010"],
    input_fields=["repository_inventory.json"],
    output_fields=["data_contract.md", "data_contract.json"],
    acceptance="data_contract.json has keys: ply_element, has_xyz, has_label_ch, "
               "label_dtype, class_mapping, train_files, val_files, test_files",
)

VAL_120 = ValidationNode(
    node_id="VAL-120",
    name="METRIC_STATIC_AUDIT",
    version="0.1.0",
    description="Check mIoU_ch implementation, whether Unchanged (class 0) is excluded, "
                "patch/cylinder/full-PC/full-resolution/voting distinction, "
                "checkpoint selection metric, historical metric口径.",
    capability_ids=["Metric Protocol Auditor"],
    module="cvo.metric_static_audit",
    callable="cvo.metric_static_audit:run",
    timeout_seconds=300,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-010"],
    input_fields=["repository_inventory.json"],
    output_fields=["metric_static_audit.md", "metric_protocol_audit.md"],
    acceptance="metric_protocol_audit.md exists; miou_ch computation excludes class 0; "
               "full-PC vs patch distinction is documented; metric names do not conflict",
)

VAL_130 = ValidationNode(
    node_id="VAL-130",
    name="MODE_CONTROLLER_AUDIT",
    version="0.1.0",
    description="Check four modes (SMOKE_CHECK, FAST_EXPLORATION, STRICT_CONFIRMATION, "
                "STATISTICAL_REPRODUCTION) and AUTO. Check mode gating, "
                "mode switching reasons are logged.",
    capability_ids=["Training Mode Controller"],
    module="cvo.mode_controller_audit",
    callable="cvo.mode_controller_audit:run",
    timeout_seconds=300,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-010"],
    input_fields=["repository_inventory.json"],
    output_fields=["mode_controller_audit.md"],
    acceptance="mode_controller_audit.md lists all 5 modes; each has entry point; "
               "mode gating exists; mode_switches are logged",
)

VAL_140 = ValidationNode(
    node_id="VAL-140",
    name="STUB_HARDCODE_SCAN",
    version="0.1.0",
    description="Scan all Python files for stub, mock, dummy, random, simulate, "
                "hardcode patterns. Requires human context analysis — "
                "not keyword-only judgment.",
    capability_ids=["Real Smoke Test"],
    module="cvo.stub_scan",
    callable="cvo.stub_scan:run",
    timeout_seconds=300,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-010"],
    input_fields=["repository_inventory.json"],
    output_fields=["stub_and_hardcode_scan.md"],
    acceptance="stub_and_hardcode_scan.md lists findings with file, line, category, "
               "context snippet, human_verdict_required flag",
)

VAL_150 = ValidationNode(
    node_id="VAL-150",
    name="EVIDENCE_CHAIN_AUDIT",
    version="0.1.0",
    description="Check run_id, resolved config, raw metrics, runs_manifest.csv, "
                "chart traceability, no simulation/hardcode in charts.",
    capability_ids=["Evidence and Provenance Manager"],
    module="cvo.evidence_chain_audit",
    callable="cvo.evidence_chain_audit:run",
    timeout_seconds=300,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-020"],
    input_fields=["artifact_inventory.json"],
    output_fields=["evidence_chain_audit.md"],
    acceptance="evidence_chain_audit.md exists; all artifacts belong to same run_id; "
               "charts trace to raw data; no hardcoded metrics in charts",
)

VAL_160 = ValidationNode(
    node_id="VAL-160",
    name="SCHEDULER_AUDIT",
    version="0.1.0",
    description="Check heartbeat, retry, pause, resume, atomic state write, "
                "OOM handling, crash recovery, agent restart recovery, "
                "checkpoint recovery, passed tasks not re-executed.",
    capability_ids=["Durable Scheduler"],
    module="cvo.scheduler_audit",
    callable="cvo.scheduler_audit:run",
    timeout_seconds=300,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-010"],
    input_fields=["repository_inventory.json"],
    output_fields=["scheduler_audit.md"],
    acceptance="scheduler_audit.md covers all 13 scheduler requirements listed above",
)

VAL_170 = ValidationNode(
    node_id="VAL-170",
    name="CLI_CURSOR_AUDIT",
    version="0.1.0",
    description="Check CLI and Cursor share the same backend. "
                "List reproctl commands. Verify commands/repro-audit.md exists.",
    capability_ids=["Cursor, CLI and Reporting"],
    module="cvo.cli_cursor_audit",
    callable="cvo.cli_cursor_audit:run",
    timeout_seconds=300,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-010"],
    input_fields=["repository_inventory.json"],
    output_fields=["cli_cursor_audit.md"],
    acceptance="cli_cursor_audit.md lists all reproctl subcommands; "
               "Cursor commands exist; both call the same backend module",
)

VAL_180 = ValidationNode(
    node_id="VAL-180",
    name="CI_AUDIT",
    version="0.1.0",
    description="Check unit tests, integration tests, regression tests. "
                "Verify tests cover config parsing, metric calculation, "
                "stub detection, mode switching, checkpoint recovery.",
    capability_ids=["CI and Regression Tests"],
    module="cvo.ci_audit",
    callable="cvo.ci_audit:run",
    timeout_seconds=300,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-010"],
    input_fields=["repository_inventory.json"],
    output_fields=["ci_audit.md"],
    acceptance="ci_audit.md lists test files and coverage per area; "
               "CI does NOT auto-trigger full training",
)


# ── Stage C: Low-Cost Runtime Verification ────────────────────────────────────

VAL_200 = ValidationNode(
    node_id="VAL-200",
    name="CONFIG_DRY_RUN",
    version="0.1.0",
    description="Parse configuration, output resolved config. "
                "Do not load full data or start training.",
    capability_ids=["Protocol Registry"],
    module="cvo.config_dry_run",
    callable="cvo.config_dry_run:run",
    timeout_seconds=300,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-100", "VAL-110", "VAL-120"],
    input_fields=["repository_inventory.json", "protocol_audit.md"],
    output_fields=["resolved_config.json"],
    acceptance="resolved_config.json exists and is valid JSON; "
               "no training started; no full data loaded",
)

VAL_210 = ValidationNode(
    node_id="VAL-210",
    name="METRIC_KNOWN_CASE",
    version="0.1.0",
    description="Use a hand-crafted confusion matrix with known expected IoU values. "
                "Verify class IoU and mIoU_ch recomputation. "
                "Expected values are pre-written in the test.",
    capability_ids=["Metric Protocol Auditor"],
    module="cvo.metric_known_case",
    callable="cvo.metric_known_case:run",
    timeout_seconds=60,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-120"],
    input_fields=["metric_protocol_audit.md"],
    output_fields=["metric_known_case_result.json"],
    acceptance="Known-case IoU values match within 1e-6; mIoU_ch excludes class 0; "
               "result JSON has exact_match=true",
)

VAL_220 = ValidationNode(
    node_id="VAL-220",
    name="CLI_INTEGRATION",
    version="0.1.0",
    description="Test reproctl --help, reproctl status, invalid mode, dry-run. "
                "Do not start long training.",
    capability_ids=["Cursor, CLI and Reporting"],
    module="cvo.cli_integration",
    callable="cvo.cli_integration:run",
    timeout_seconds=120,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-130", "VAL-160", "VAL-170"],
    input_fields=["cli_cursor_audit.md"],
    output_fields=["cli_integration_result.json"],
    acceptance="All CLI commands respond; invalid mode returns error; "
               "no training process started",
)

VAL_230 = ValidationNode(
    node_id="VAL-230",
    name="SCHEDULER_RECOVERY",
    version="0.1.0",
    description="Start a temporary short task, interrupt it, recover, "
                "verify already-passed nodes are not re-run.",
    capability_ids=["Durable Scheduler"],
    module="cvo.scheduler_recovery",
    callable="cvo.scheduler_recovery:run",
    timeout_seconds=300,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-130", "VAL-160", "VAL-170"],
    input_fields=["scheduler_audit.md"],
    output_fields=["scheduler_recovery_result.json"],
    acceptance="Interrupted task resumes from checkpoint; passed nodes not re-run; "
               "result JSON has recovery_success=true",
)

VAL_240 = ValidationNode(
    node_id="VAL-240",
    name="CHECKPOINT_IO",
    version="0.1.0",
    description="Create minimal test checkpoint, verify save/load integrity. "
                "Do not overwrite real checkpoints.",
    capability_ids=["Evidence and Provenance Manager"],
    module="cvo.checkpoint_io",
    callable="cvo.checkpoint_io:run",
    timeout_seconds=120,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-010"],
    input_fields=["repository_inventory.json"],
    output_fields=["checkpoint_io_result.json"],
    acceptance="Checkpoint saves and loads correctly; state matches; "
               "real checkpoints not modified",
)


# ── Stage D: Real Model Short Loop ─────────────────────────────────────────────

VAL_300 = ValidationNode(
    node_id="VAL-300",
    name="REAL_DATA_PREFLIGHT",
    version="0.1.0",
    description="Verify real data path, extract one batch, check fields, labels, "
                "shape, point count. Do NOT train.",
    capability_ids=["Real Smoke Test"],
    module="cvo.real_data_preflight",
    callable="cvo.real_data_preflight:run",
    timeout_seconds=300,
    requires_gpu=True,
    requires_real_data=True,
    depends_on=["VAL-110", "VAL-200"],
    input_fields=["data_contract.json", "resolved_config.json"],
    output_fields=["real_data_preflight_result.json"],
    acceptance="Data path accessible; batch fields (xyz, label_ch) correct; "
               "no training started; result JSON has preflight_ok=true",
    deterministically_fails=True,
)

VAL_310 = ValidationNode(
    node_id="VAL-310",
    name="REAL_BATCH_FORWARD",
    version="0.1.0",
    description="Real SiamKPConv, real DataLoader, one batch forward and loss. "
                "Verify NaN/Inf detection.",
    capability_ids=["Real Smoke Test"],
    module="cvo.real_batch_forward",
    callable="cvo.real_batch_forward:run",
    timeout_seconds=600,
    requires_gpu=True,
    requires_real_data=True,
    depends_on=["VAL-300"],
    input_fields=["real_data_preflight_result.json"],
    output_fields=["real_batch_forward_result.json"],
    acceptance="Forward pass completes; loss is finite (no NaN/Inf); "
               "result JSON has forward_ok=true, loss_is_finite=true",
    deterministically_fails=True,
)

VAL_320 = ValidationNode(
    node_id="VAL-320",
    name="REAL_BATCH_BACKWARD",
    version="0.1.0",
    description="backward() + gradient check + optimizer.step() + memory stats. "
                "Depends on VAL-310.",
    capability_ids=["Real Smoke Test"],
    module="cvo.real_batch_backward",
    callable="cvo.real_batch_backward:run",
    timeout_seconds=600,
    requires_gpu=True,
    requires_real_data=True,
    depends_on=["VAL-310"],
    input_fields=["real_batch_forward_result.json"],
    output_fields=["real_batch_backward_result.json"],
    acceptance="backward completes; gradients are non-zero; optimizer steps; "
               "no OOM; result JSON has backward_ok=true, gradients_nonzero=true",
    deterministically_fails=True,
)

VAL_330 = ValidationNode(
    node_id="VAL-330",
    name="REAL_BATCH_EVAL",
    version="0.1.0",
    description="Real prediction, confusion matrix, class IoU, mIoU_ch. "
                "Verify metrics can be recomputed from confusion matrix.",
    capability_ids=["Real Smoke Test", "Metric Protocol Auditor"],
    module="cvo.real_batch_eval",
    callable="cvo.real_batch_eval:run",
    timeout_seconds=600,
    requires_gpu=True,
    requires_real_data=True,
    depends_on=["VAL-310"],
    input_fields=["real_batch_forward_result.json"],
    output_fields=["real_batch_eval_result.json", "confmat.json"],
    acceptance="confmat.json exists (non-normalized); mIoU_ch recomputes correctly; "
               "result JSON has eval_ok=true, miou_recomputable=true",
    deterministically_fails=True,
)

VAL_340 = ValidationNode(
    node_id="VAL-340",
    name="SMOKE_100_STEPS",
    version="0.1.0",
    description="Up to 100 steps. Save lightweight state every 10 steps. "
                "Check loss trajectory, NaN, Inf, OOM, throughput.",
    capability_ids=["Real Smoke Test", "Performance and Batch Tuner"],
    module="cvo.smoke_100_steps",
    callable="cvo.smoke_100_steps:run",
    timeout_seconds=1800,
    requires_gpu=True,
    requires_real_data=True,
    depends_on=["VAL-320", "VAL-330"],
    input_fields=["real_batch_backward_result.json", "real_batch_eval_result.json"],
    output_fields=["smoke_100_steps_result.json"],
    acceptance="100 steps complete (or hit early stop on OOM/NaN); "
               "no NaN in loss; no OOM crashes; result JSON has steps_completed, "
               "loss_finite, oom_count, steps_per_second",
    deterministically_fails=True,
)

VAL_350 = ValidationNode(
    node_id="VAL-350",
    name="SMOKE_EPOCH_1",
    version="0.1.0",
    description="Run first short epoch. Save checkpoint and metrics.",
    capability_ids=["Real Smoke Test", "Evidence and Provenance Manager"],
    module="cvo.smoke_epoch",
    callable="cvo.smoke_epoch:run",
    timeout_seconds=3600,
    requires_gpu=True,
    requires_real_data=True,
    depends_on=["VAL-340"],
    input_fields=["smoke_100_steps_result.json"],
    output_fields=["smoke_epoch_1_result.json", "checkpoint_epoch_1.pt"],
    acceptance="Epoch 1 completes; checkpoint saves; metrics CSV generated; "
               "result JSON has epoch_completed=true",
    deterministically_fails=True,
)

VAL_351 = ValidationNode(
    node_id="VAL-351",
    name="SMOKE_EPOCH_2",
    version="0.1.0",
    description="Resume from VAL-350 checkpoint. Run second epoch.",
    capability_ids=["Real Smoke Test", "Evidence and Provenance Manager"],
    module="cvo.smoke_epoch",
    callable="cvo.smoke_epoch:run",
    timeout_seconds=3600,
    requires_gpu=True,
    requires_real_data=True,
    depends_on=["VAL-350"],
    input_fields=["smoke_epoch_1_result.json", "checkpoint_epoch_1.pt"],
    output_fields=["smoke_epoch_2_result.json", "checkpoint_epoch_2.pt"],
    acceptance="Resume from checkpoint succeeds; epoch 2 completes; "
               "metrics continue from epoch 1; result JSON has resume_ok=true",
    deterministically_fails=True,
)

VAL_352 = ValidationNode(
    node_id="VAL-352",
    name="SMOKE_EPOCH_3",
    version="0.1.0",
    description="Third epoch. Only if first two epochs were stable.",
    capability_ids=["Real Smoke Test"],
    module="cvo.smoke_epoch",
    callable="cvo.smoke_epoch:run",
    timeout_seconds=3600,
    requires_gpu=True,
    requires_real_data=True,
    depends_on=["VAL-351"],
    input_fields=["smoke_epoch_2_result.json"],
    output_fields=["smoke_epoch_3_result.json"],
    acceptance="Third epoch completes; loss trajectory consistent; "
               "result JSON has epoch_completed=true",
    deterministically_fails=True,
    retryable=True,
)


# ── Stage E: Performance Probing ────────────────────────────────────────────────

VAL_400 = ValidationNode(
    node_id="VAL-400",
    name="PERFORMANCE_PREFLIGHT",
    version="0.1.0",
    description="Confirm GPU info, build batch candidate list. "
                "Do NOT directly run all candidates.",
    capability_ids=["Performance and Batch Tuner"],
    module="cvo.perf_preflight",
    callable="cvo.perf_preflight:run",
    timeout_seconds=120,
    requires_gpu=True,
    requires_real_data=True,
    depends_on=["VAL-320"],
    input_fields=["real_batch_backward_result.json"],
    output_fields=["perf_preflight_result.json", "batch_candidates.json"],
    acceptance="GPU info captured; batch candidates list is non-empty; "
               "no actual batch probing started yet",
)

# Individual batch candidates — VAL-410-BS{n}
_BS_CANDIDATES = [10, 12, 16, 20, 24, 32, 40]
VAL_BATCH_NODES: list[ValidationNode] = []
for bs in _BS_CANDIDATES:
    node = ValidationNode(
        node_id=f"VAL-410-BS{bs}",
        name=f"PERF_BATCH_SEARCH_BS{bs}",
        version="0.1.0",
        description=f"Run forward+backward+optimizer.step with batch_size={bs}. "
                    f"OOM only marks this candidate failed. Independent subprocess.",
        capability_ids=["Performance and Batch Tuner"],
        module="cvo.perf_batch_trial",
        callable="cvo.perf_batch_trial:run",
        timeout_seconds=600,
        requires_gpu=True,
        requires_real_data=True,
        depends_on=["VAL-400"],
        input_fields=["perf_preflight_result.json"],
        output_fields=[f"trial_bs{bs}.json"],
        acceptance=f"trial_bs{bs}.json exists with status (ok/oom/error) and "
                   f"step_time_mean_s; result is isolated from other batch candidates",
        deterministically_fails=False,
    )
    VAL_BATCH_NODES.append(node)

VAL_420 = ValidationNode(
    node_id="VAL-420",
    name="PERFORMANCE_AGGREGATE",
    version="0.1.0",
    description="Aggregate all batch candidates. Output paper_batch, max_feasible_batch, "
                "best_throughput_batch, recommended_batch. No model execution.",
    capability_ids=["Performance and Batch Tuner"],
    module="cvo.perf_aggregate",
    callable="cvo.perf_aggregate:run",
    timeout_seconds=60,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=[f"VAL-410-BS{bs}" for bs in _BS_CANDIDATES],
    input_fields=[f"trial_bs{bs}.json" for bs in _BS_CANDIDATES],
    output_fields=["perf_aggregate_result.json", "perf_aggregate.md"],
    acceptance="perf_aggregate_result.json has paper_batch, max_feasible_batch, "
               "best_throughput_batch, recommended_batch; "
               "recommended_batch is best_throughput, not max batch",
)


# ── Stage F: Final Summary ─────────────────────────────────────────────────────

VAL_500 = ValidationNode(
    node_id="VAL-500",
    name="CAPABILITY_AGGREGATE",
    version="0.1.0",
    description="Aggregate all node statuses. Update capability_matrix.csv. "
                "Do not re-run completed tests.",
    capability_ids=["CVO"],
    module="cvo.capability_aggregate",
    callable="cvo.capability_aggregate:run",
    timeout_seconds=300,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=[
        "VAL-100", "VAL-110", "VAL-120", "VAL-130", "VAL-140",
        "VAL-150", "VAL-160", "VAL-170", "VAL-180",
        "VAL-200", "VAL-210", "VAL-220", "VAL-230", "VAL-240",
        "VAL-300", "VAL-310", "VAL-320", "VAL-330", "VAL-340",
        "VAL-350", "VAL-351", "VAL-352",
        "VAL-400", "VAL-420",
    ],
    input_fields=["nodes/*.json"],
    output_fields=["capability_matrix.csv", "capability_manifest.json"],
    acceptance="capability_matrix.csv exists with all 90+ rows; "
               "each row has capability_id, status, verification_level, evidence_files",
)

VAL_510 = ValidationNode(
    node_id="VAL-510",
    name="GAP_CLASSIFICATION",
    version="0.1.0",
    description="Classify all capabilities into MISSING, PARTIAL, STUB, BROKEN, BLOCKED. "
                "Assign P0/P1/P2/P3 severity.",
    capability_ids=["CVO"],
    module="cvo.gap_classification",
    callable="cvo.gap_classification:run",
    timeout_seconds=300,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-500"],
    input_fields=["capability_matrix.csv"],
    output_fields=["missing_features.md", "partial_features.md"],
    acceptance="missing_features.md has P0/P1/P2/P3 sections; "
               "partial_features.md lists incomplete features",
)

VAL_520 = ValidationNode(
    node_id="VAL-520",
    name="READINESS_GATE",
    version="0.1.0",
    description="Determine if FAST or STRICT training can be started. "
                "List blocking items explicitly.",
    capability_ids=["CVO"],
    module="cvo.readiness_gate",
    callable="cvo.readiness_gate:run",
    timeout_seconds=60,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-510"],
    input_fields=["missing_features.md", "partial_features.md"],
    output_fields=["readiness_gate_result.json"],
    acceptance="readiness_gate_result.json has can_start_fast, can_start_strict, "
               "blocking_items list; explicit GO/NO-GO decision",
)

VAL_530 = ValidationNode(
    node_id="VAL-530",
    name="FINAL_REPORT",
    version="0.1.0",
    description="Generate final Chinese Markdown + JSON + CSV + HTML report. "
                "Report reads only previous node evidence.",
    capability_ids=["CVO"],
    module="cvo.final_report",
    callable="cvo.final_report:run",
    timeout_seconds=300,
    requires_gpu=False,
    requires_real_data=False,
    depends_on=["VAL-520"],
    input_fields=["readiness_gate_result.json", "capability_matrix.csv", "missing_features.md"],
    output_fields=[
        "final_report.md",
        "final_report.json",
        "final_report.html",
        "verification_summary.html",
    ],
    acceptance="final_report.md exists with all sections; final_report.json has "
               "summary statistics; verification_summary.html is renderable",
)


# ── Registry ───────────────────────────────────────────────────────────────────

ALL_NODES: list[ValidationNode] = [
    # Stage A
    VAL_000, VAL_010, VAL_020,
    # Stage B
    VAL_100, VAL_110, VAL_120, VAL_130, VAL_140,
    VAL_150, VAL_160, VAL_170, VAL_180,
    # Stage C
    VAL_200, VAL_210, VAL_220, VAL_230, VAL_240,
    # Stage D
    VAL_300, VAL_310, VAL_320, VAL_330, VAL_340,
    VAL_350, VAL_351, VAL_352,
    # Stage E
    VAL_400,
    *VAL_BATCH_NODES,
    VAL_420,
    # Stage F
    VAL_500, VAL_510, VAL_520, VAL_530,
]

NODE_MAP: dict[str, ValidationNode] = {n.node_id: n for n in ALL_NODES}

# Stage labels
STAGE_LABELS: dict[str, str] = {
    "A": "Project Discovery",
    "B": "Static Functional Audit",
    "C": "Low-Cost Runtime Verification",
    "D": "Real Model Short Loop",
    "E": "Performance Probing",
    "F": "Final Summary",
}

STAGE_NODES: dict[str, list[str]] = {
    "A": ["VAL-000", "VAL-010", "VAL-020"],
    "B": ["VAL-100", "VAL-110", "VAL-120", "VAL-130", "VAL-140",
           "VAL-150", "VAL-160", "VAL-170", "VAL-180"],
    "C": ["VAL-200", "VAL-210", "VAL-220", "VAL-230", "VAL-240"],
    "D": ["VAL-300", "VAL-310", "VAL-320", "VAL-330", "VAL-340",
           "VAL-350", "VAL-351", "VAL-352"],
    "E": ["VAL-400"] + [f"VAL-410-BS{bs}" for bs in _BS_CANDIDATES] + ["VAL-420"],
    "F": ["VAL-500", "VAL-510", "VAL-520", "VAL-530"],
}


def get_node(node_id: str) -> ValidationNode | None:
    return NODE_MAP.get(node_id)


def get_stage(node_id: str) -> str:
    prefix = node_id.split("-")[0]
    return STAGE_LABELS.get(prefix, "Unknown")


def get_next_ready() -> list[ValidationNode]:
    """Return all nodes whose dependencies are satisfied and are not yet PASSED."""
    # Import state lazily to avoid circular imports
    from cvo.state import CVOStateStore
    try:
        store = CVOStateStore()
    except Exception:
        return []

    ready = []
    for node in ALL_NODES:
        status = store.get_status(node.node_id)
        if status in ("PASSED", "RUNNING", "PAUSED"):
            continue
        deps_satisfied = all(
            store.get_status(dep) == "PASSED"
            for dep in node.depends_on
        )
        if deps_satisfied:
            ready.append(node)
    return ready
