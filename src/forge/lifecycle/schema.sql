-- Forge SQLite schema (TASK-PSM-002).
--
-- Source of truth: docs/design/contracts/API-sqlite-schema.md and
-- docs/design/decisions/DDR-003-sqlite-schema-layout-wal.md.
--
-- All tables are STRICT (SQLite >= 3.37) so Pydantic-driven writes
-- surface type drift at write time rather than silently round-tripping
-- as TEXT. CREATE TABLE IF NOT EXISTS makes the file safe to re-run
-- on every boot — this is the idempotency contract that
-- forge.lifecycle.migrations.apply_at_boot relies on.

-- =====================================================================
-- 2.1 builds — one row per build attempt, lifecycle-tracked
-- =====================================================================
CREATE TABLE IF NOT EXISTS builds (
    build_id TEXT PRIMARY KEY,                       -- build-{feature_id}-{YYYYMMDDHHMMSS}
    feature_id TEXT NOT NULL,
    repo TEXT NOT NULL,
    branch TEXT NOT NULL,
    feature_yaml_path TEXT NOT NULL,
    project TEXT,                                    -- NULL = fleet-wide

    status TEXT NOT NULL CHECK (status IN (
        'QUEUED', 'PREPARING', 'RUNNING', 'PAUSED', 'FINALISING',
        'COMPLETE', 'FAILED', 'INTERRUPTED', 'CANCELLED', 'SKIPPED'
    )),

    triggered_by TEXT NOT NULL CHECK (triggered_by IN (
        'cli', 'jarvis', 'forge-internal', 'notification-adapter'
    )),
    originating_adapter TEXT,
    originating_user TEXT,
    correlation_id TEXT NOT NULL,
    parent_request_id TEXT,                          -- Jarvis dispatch ID

    queued_at TEXT NOT NULL,                         -- ISO 8601 UTC
    started_at TEXT,
    completed_at TEXT,

    worktree_path TEXT,
    pr_url TEXT,
    error TEXT,

    max_turns INTEGER NOT NULL DEFAULT 5,
    sdk_timeout_seconds INTEGER NOT NULL DEFAULT 1800,

    -- Review finding F4: PAUSED-state crash recovery must re-issue the
    -- approval request with the original request_id. Populated only
    -- while status='PAUSED'. Producer side of the
    -- PENDING_APPROVAL_REQUEST_ID integration contract (TASK-PSM-007).
    pending_approval_request_id TEXT
) STRICT;

CREATE INDEX IF NOT EXISTS idx_builds_feature
    ON builds (feature_id, queued_at DESC);

CREATE INDEX IF NOT EXISTS idx_builds_status
    ON builds (status, queued_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_builds_feature_correlation
    ON builds (feature_id, correlation_id);

-- =====================================================================
-- 2.2 stage_log — many rows per build, one per dispatched stage
-- =====================================================================
CREATE TABLE IF NOT EXISTS stage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_id TEXT NOT NULL REFERENCES builds(build_id),

    stage_label TEXT NOT NULL,
    target_kind TEXT NOT NULL CHECK (target_kind IN (
        'local_tool', 'fleet_capability', 'subagent'
    )),
    target_identifier TEXT NOT NULL,

    status TEXT NOT NULL CHECK (status IN (
        'PASSED', 'FAILED', 'GATED', 'SKIPPED'
    )),
    gate_mode TEXT CHECK (gate_mode IN (
        'AUTO_APPROVE', 'FLAG_FOR_REVIEW', 'HARD_STOP', 'MANDATORY_HUMAN_APPROVAL'
    )),

    coach_score REAL,
    threshold_applied REAL,

    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    duration_secs REAL NOT NULL,

    details_json TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_stage_log_build
    ON stage_log (build_id, started_at);

CREATE INDEX IF NOT EXISTS idx_stage_log_gated
    ON stage_log (build_id, gate_mode)
    WHERE gate_mode IS NOT NULL;

-- =====================================================================
-- 2.3 schema_version — explicit, sequential migration ledger
-- =====================================================================
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
) STRICT;

INSERT OR IGNORE INTO schema_version (version, applied_at)
VALUES (1, datetime('now'));
