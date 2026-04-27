-- Forge SQLite schema v2 (TASK-MBC8-001).
--
-- Additive migration that adds the ``mode`` column to the ``builds``
-- table introduced in v1 (schema.sql). Backfill is the literal default
-- ``'mode-a'`` so historical Mode A rows stay valid through the
-- FEAT-FORGE-008 upgrade window with zero data movement.
--
-- This script is **delta-only**: schema.sql remains the v1 baseline
-- and never references the ``mode`` column. The migrations runner
-- (``forge.lifecycle.migrations.apply_at_boot``) executes both v1 and
-- v2 against a fresh database in order, so the only path to a
-- mode-bearing ``builds`` table goes through this script. That keeps
-- the column-add idempotent: existing databases at v1 receive the
-- ALTER, brand-new databases run schema.sql then this script, and
-- already-v2 databases see this script gated out by the schema_version
-- ledger entry below.
--
-- SQLite-specific note: ``ALTER TABLE ... ADD COLUMN`` is not
-- IF-NOT-EXISTS-aware, so the runner relies on the schema_version
-- ledger to ensure this script only runs once per database.

ALTER TABLE builds
    ADD COLUMN mode TEXT NOT NULL DEFAULT 'mode-a'
    CHECK (mode IN ('mode-a', 'mode-b', 'mode-c'));

INSERT OR IGNORE INTO schema_version (version, applied_at)
VALUES (2, datetime('now'));
