"""Tests for ``forge.config.QueueConfig`` and ``forge.config.load_config``.

Each test class mirrors one acceptance criterion of TASK-PSM-003 so the
mapping between criterion and verifier stays explicit (per the project's
testing rules — AAA pattern, descriptive names, AC traceability).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from forge.config import ForgeConfig, QueueConfig, load_config

# ---------------------------------------------------------------------------
# AC-001: QueueConfig exists with the four fields
# ---------------------------------------------------------------------------


class TestQueueConfigExists:
    """AC-001: ``QueueConfig`` exposes the four required fields."""

    def test_queue_config_has_default_max_turns_field(self) -> None:
        assert "default_max_turns" in QueueConfig.model_fields

    def test_queue_config_has_default_sdk_timeout_seconds_field(self) -> None:
        assert "default_sdk_timeout_seconds" in QueueConfig.model_fields

    def test_queue_config_has_default_history_limit_field(self) -> None:
        assert "default_history_limit" in QueueConfig.model_fields

    def test_queue_config_has_repo_allowlist_field(self) -> None:
        assert "repo_allowlist" in QueueConfig.model_fields

    def test_queue_config_defaults_match_spec(self) -> None:
        cfg = QueueConfig()
        assert cfg.default_max_turns == 5
        assert cfg.default_sdk_timeout_seconds == 1800
        assert cfg.default_history_limit == 50
        assert cfg.repo_allowlist == []


# ---------------------------------------------------------------------------
# AC-002: ForgeConfig.queue uses a default factory
# ---------------------------------------------------------------------------


class TestForgeConfigHasQueueWithDefaultFactory:
    """AC-002: ``ForgeConfig.queue`` is populated by a default factory."""

    def test_forge_config_has_queue_field(self) -> None:
        assert "queue" in ForgeConfig.model_fields

    def test_forge_config_queue_default_isolated_per_instance(self) -> None:
        a = ForgeConfig.model_validate(
            {"permissions": {"filesystem": {"allowlist": ["/srv/forge"]}}}
        )
        b = ForgeConfig.model_validate(
            {"permissions": {"filesystem": {"allowlist": ["/srv/forge"]}}}
        )
        # default_factory must hand out a fresh repo_allowlist list per instance
        a.queue.repo_allowlist.append(Path("/intruder"))
        assert Path("/intruder") not in b.queue.repo_allowlist


# ---------------------------------------------------------------------------
# AC-003: load_config(path) reads YAML via yaml.safe_load
# ---------------------------------------------------------------------------


class TestLoadConfigReadsYaml:
    """AC-003: ``load_config`` uses ``yaml.safe_load`` and returns ForgeConfig."""

    def test_load_config_returns_forge_config(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "forge.yaml"
        yaml_path.write_text(
            yaml.safe_dump(
                {
                    "permissions": {"filesystem": {"allowlist": ["/srv/forge"]}},
                    "queue": {"default_max_turns": 7},
                }
            )
        )

        cfg = load_config(yaml_path)

        assert isinstance(cfg, ForgeConfig)
        assert cfg.queue.default_max_turns == 7

    def test_load_config_uses_safe_load_not_full_load(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Spy on yaml.safe_load to assert the loader uses *that* function
        # rather than the unsafe yaml.load / yaml.full_load variants.
        called: dict[str, bool] = {"safe_load": False}
        original_safe_load = yaml.safe_load

        def _spy(stream: object) -> object:
            called["safe_load"] = True
            return original_safe_load(stream)

        monkeypatch.setattr("forge.config.loader.yaml.safe_load", _spy)

        yaml_path = tmp_path / "forge.yaml"
        yaml_path.write_text(
            yaml.safe_dump(
                {"permissions": {"filesystem": {"allowlist": ["/srv/forge"]}}}
            )
        )

        load_config(yaml_path)

        assert called["safe_load"] is True


# ---------------------------------------------------------------------------
# AC-004: load_config raises pydantic.ValidationError unwrapped
# ---------------------------------------------------------------------------


class TestLoadConfigRaisesValidationError:
    """AC-004: malformed YAML surfaces ``ValidationError`` directly."""

    def test_missing_required_permissions_raises_validation_error(
        self, tmp_path: Path
    ) -> None:
        yaml_path = tmp_path / "forge.yaml"
        yaml_path.write_text(yaml.safe_dump({}))

        with pytest.raises(ValidationError):
            load_config(yaml_path)

    def test_validation_error_is_not_wrapped(self, tmp_path: Path) -> None:
        # The CLI catches ``ValidationError`` directly to format ``.errors()``.
        # If the loader wrapped the exception (e.g. in a custom ConfigError),
        # this assertion would fail and the contract with TASK-PSM-008..011
        # would be silently broken.
        yaml_path = tmp_path / "forge.yaml"
        yaml_path.write_text(
            yaml.safe_dump(
                {
                    "permissions": {"filesystem": {"allowlist": ["/srv/forge"]}},
                    "queue": {"default_max_turns": 0},
                }
            )
        )

        with pytest.raises(ValidationError) as exc_info:
            load_config(yaml_path)

        # Confirm we got the *exact* class, not a subclass-via-wrapper.
        assert exc_info.type is ValidationError


# ---------------------------------------------------------------------------
# AC-005: default_max_turns: 0 in YAML raises ValidationError
# ---------------------------------------------------------------------------


class TestDefaultMaxTurnsZeroRejected:
    """AC-005: turn budget below the ASSUM-001 minimum is rejected."""

    def test_default_max_turns_zero_raises(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "forge.yaml"
        yaml_path.write_text(
            yaml.safe_dump(
                {
                    "permissions": {"filesystem": {"allowlist": ["/srv/forge"]}},
                    "queue": {"default_max_turns": 0},
                }
            )
        )

        with pytest.raises(ValidationError) as exc_info:
            load_config(yaml_path)

        errors = exc_info.value.errors()
        assert any(
            err["loc"] == ("queue", "default_max_turns")
            and err["type"] in {"greater_than_equal", "value_error"}
            for err in errors
        ), f"Expected ge=1 violation on queue.default_max_turns; got {errors!r}"


# ---------------------------------------------------------------------------
# AC-006: default_max_turns: 1 accepted (ASSUM-001 minimum)
# ---------------------------------------------------------------------------


class TestDefaultMaxTurnsOneAccepted:
    """AC-006: a turn budget of exactly 1 is accepted."""

    def test_default_max_turns_one_accepted(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "forge.yaml"
        yaml_path.write_text(
            yaml.safe_dump(
                {
                    "permissions": {"filesystem": {"allowlist": ["/srv/forge"]}},
                    "queue": {"default_max_turns": 1},
                }
            )
        )

        cfg = load_config(yaml_path)

        assert cfg.queue.default_max_turns == 1


# ---------------------------------------------------------------------------
# AC-007: missing queue: block — ForgeConfig.queue populated from defaults
# ---------------------------------------------------------------------------


class TestMissingQueueBlockUsesDefaults:
    """AC-007: omitting ``queue:`` in YAML still yields a populated QueueConfig."""

    def test_missing_queue_block_populates_defaults(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "forge.yaml"
        yaml_path.write_text(
            yaml.safe_dump(
                {"permissions": {"filesystem": {"allowlist": ["/srv/forge"]}}}
            )
        )

        cfg = load_config(yaml_path)

        assert isinstance(cfg.queue, QueueConfig)
        assert cfg.queue.default_max_turns == 5
        assert cfg.queue.default_sdk_timeout_seconds == 1800
        assert cfg.queue.default_history_limit == 50
        assert cfg.queue.repo_allowlist == []


# ---------------------------------------------------------------------------
# AC-008: repo_allowlist: ["/home/rich/Projects"] parses to list[Path]
# ---------------------------------------------------------------------------


class TestRepoAllowlistParsesToPaths:
    """AC-008: YAML strings under ``repo_allowlist`` become ``Path`` instances."""

    def test_repo_allowlist_string_parses_to_path(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "forge.yaml"
        yaml_path.write_text(
            yaml.safe_dump(
                {
                    "permissions": {"filesystem": {"allowlist": ["/srv/forge"]}},
                    "queue": {"repo_allowlist": ["/home/rich/Projects"]},
                }
            )
        )

        cfg = load_config(yaml_path)

        assert cfg.queue.repo_allowlist == [Path("/home/rich/Projects")]
        assert all(isinstance(p, Path) for p in cfg.queue.repo_allowlist)

    def test_repo_allowlist_multiple_paths(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "forge.yaml"
        yaml_path.write_text(
            yaml.safe_dump(
                {
                    "permissions": {"filesystem": {"allowlist": ["/srv/forge"]}},
                    "queue": {
                        "repo_allowlist": [
                            "/home/rich/Projects",
                            "/var/repos/forge",
                        ]
                    },
                }
            )
        )

        cfg = load_config(yaml_path)

        assert cfg.queue.repo_allowlist == [
            Path("/home/rich/Projects"),
            Path("/var/repos/forge"),
        ]
