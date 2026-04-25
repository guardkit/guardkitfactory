"""Integration test suite for FEAT-FORGE-004 (TASK-CGCP-011).

Contract + seam tests for the approval round-trip across NATS. The
``conftest.py`` sibling exposes the in-memory NATS double, an in-memory
SQLite-shaped repository, and the deterministic clock injected into
every test in this directory.
"""
