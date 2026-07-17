"""OSTAR constants: exit codes, statuses, defaults, and termination conditions."""
from __future__ import annotations

import zoneinfo

# ─────────────────────────────────────────────────────────────────────────────
# Exit codes  (align with startup/cli.py convention)
# ─────────────────────────────────────────────────────────────────────────────

EXIT_OK = 0
EXIT_BAD_CONFIG = 2
EXIT_GUARD_FAIL = 3          # pre-flight protection check failed
EXIT_ALREADY_RUNNING = 4
EXIT_REHEARSAL_FAIL = 5       # pre-flight rehearsal failed
EXIT_TEST_FAILED = 6
EXIT_REPAIR_EXHAUSTED = 7    # max repairs reached
EXIT_RESUME_FAILED = 8
EXIT_HARDWARE_SAFETY = 9      # GPU temp / disk / hardware limit exceeded
EXIT_INTERNAL = 10
EXIT_MANUAL_STOP = 11
EXIT_DURATION_ENDED = 12

# ─────────────────────────────────────────────────────────────────────────────
# Soak run statuses
# ─────────────────────────────────────────────────────────────────────────────

SOAK_STATUSES = {
    "INIT", "RUNNING", "PAUSED", "RESUMING", "REHEARSING",
    "COMPLETED", "FAILED", "ABORTED", "STOPPED",
}
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "ABORTED", "STOPPED"}

# ─────────────────────────────────────────────────────────────────────────────
# Loop node statuses
# ─────────────────────────────────────────────────────────────────────────────

NODE_STATUSES = {
    "PENDING", "RUNNING", "PASS", "FAIL", "SKIP",
    "REPAIRING", "REPAIRED", "ROLLBACK", "BLOCKED",
}

# ─────────────────────────────────────────────────────────────────────────────
# Final verdict statuses (from Section X)
# ─────────────────────────────────────────────────────────────────────────────

VERDICT_SOAK_VERIFIED = "SOAK_VERIFIED"
VERDICT_REPAIRED_NOT_SOAK_VERIFIED = "REPAIRED_BUT_NOT_SOAK_VERIFIED"
VERDICT_FAILED_UNRESOLVED = "FAILED_WITH_UNRESOLVED_BUGS"
VERDICT_BLOCKED_REQUIRES_REVIEW = "BLOCKED_REQUIRES_REVIEW"
VERDICT_ABORTED_HARDWARE = "ABORTED_FOR_HARDWARE_SAFETY"

# ─────────────────────────────────────────────────────────────────────────────
# Error classification
# ─────────────────────────────────────────────────────────────────────────────

ERROR_CLASSES = {
    "CODE",        # plain code bug
    "CONFIG",      # path / config parsing
    "RESOURCE",    # resource leak / not released
    "STATE",       # atomic-write / state-file corruption
    "CLI",         # CLI argument wiring
    "CHECKPOINT",  # checkpoint I/O
    "RECOVERY",    # recovery logic error
    "FIXTURE",     # test fixture error
    "METRIC",      # metric implementation (protocol-supported)
    "ENVIRONMENT", # env / import
    "INTERMITTENT",# flaky / non-deterministic
    "PROTOCOL",    # paper protocol violation
    "DATA",        # dataset / split / label
    "UNKNOWN",
}

# BLOCKED_REQUIRES_REVIEW — never auto-repair
BLOCKED_CLASSES = {"PROTOCOL", "DATA", "MODEL", "LOSS", "SCHEDULER"}

# Allowed per AUTO_REPAIR_SAFE
AUTO_REPAIR_CLASSES = {
    "CODE", "CONFIG", "RESOURCE", "STATE", "CLI",
    "CHECKPOINT", "RECOVERY", "FIXTURE", "METRIC", "ENVIRONMENT",
}

# ─────────────────────────────────────────────────────────────────────────────
# Default values
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_TIMEZONE = "Asia/Singapore"
DEFAULT_DURATION_SECONDS = 8 * 3600          # 8 hours
DEFAULT_MAX_REPAIRS = 10
DEFAULT_MAX_RETRIES_PER_BUG = 3              # per-error max attempts
DEFAULT_MAX_CONSECUTIVE_CRASHES = 3
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 30
DEFAULT_CHECKPOINT_INTERVAL_SECONDS = 30
DEFAULT_GPU_WARN_TEMP_C = 82                 # warn at 82°C (conservative guard)
DEFAULT_GPU_CRITICAL_TEMP_C = 87            # stop GPU tests at 87°C
DEFAULT_DISK_RESERVE_GB = 10                # min free GB on disk
DEFAULT_GPU_MEMORY_RESERVE_PCT = 15         # keep 15% GPU memory headroom
DEFAULT_SOAK_RUN_ID_PREFIX = "soak"

# Rehearsal duration (30 minutes = 1800 seconds)
DEFAULT_REHEARSAL_DURATION_SECONDS = 30 * 60

# Stability verification: last 2 hours of calm before declaring SOAK_VERIFIED
STABILITY_WINDOW_SECONDS = 2 * 3600

# ─────────────────────────────────────────────────────────────────────────────
# Termination conditions
# ─────────────────────────────────────────────────────────────────────────────

TERMINATION_DEADLINES = {
    "end_time_reached",
    "max_repairs_reached",
    "same_bug_consecutive_failures",
    "p0_unresolved",
    "git_workdir_unsafe",
    "gpu_temperature_exceeded",
    "disk_space_below_reserve",
    "state_file_corrupt",
    "consecutive_agent_crashes",
}

# ─────────────────────────────────────────────────────────────────────────────
# Batch boundary test candidates
# ─────────────────────────────────────────────────────────────────────────────

BATCH_BOUNDARY_CANDIDATES = [
    "paper_batch",
    "recommended_batch",
    "recommended_batch_minus_one",
    "recommended_batch_plus_one",
    "p95_points_batch",
    "max_points_batch",
]

# ─────────────────────────────────────────────────────────────────────────────
# DataLoader stress parameters
# ─────────────────────────────────────────────────────────────────────────────

DATALOADER_WORKER_COUNTS = [0, 2, 4, 8]
DATALOADER_PREFETCH_FACTORS = [2, 4]
DATALOADER_PIN_MEMORY_OPTIONS = [False, True]
DATALOADER_PERSISTENT_OPTIONS = [False, True]

# ─────────────────────────────────────────────────────────────────────────────
# Auto-repair-level enum
# ─────────────────────────────────────────────────────────────────────────────

AUTO_REPAIR_LEVELS = {"none", "safe", "full"}

# ─────────────────────────────────────────────────────────────────────────────
# Timezone helper
# ─────────────────────────────────────────────────────────────────────────────

def get_tz(tz_name: str | None = None) -> zoneinfo.ZoneInfo:
    """Return a ZoneInfo for the given name or DEFAULT_TIMEZONE."""
    return zoneinfo.ZoneInfo(tz_name or DEFAULT_TIMEZONE)
