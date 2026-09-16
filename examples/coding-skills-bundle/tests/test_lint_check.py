"""Command-line behavior tests for the bundled Python syntax checker."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BUNDLE_ROOT = Path(__file__).resolve().parents[1]
HELPER = BUNDLE_ROOT / "skills" / "code-review" / "lint_check.py"


class SyntaxCheckCliTests(unittest.TestCase):
    """Exercise the helper only through its public command-line interface."""

    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary_directory.cleanup)
        self.root = Path(self._temporary_directory.name) / "root"
        self.root.mkdir()

    def run_helper(
        self,
        *paths: str,
        root: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run the helper without creating bytecode or importing checked files."""
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(HELPER),
                "--root",
                str(root or self.root),
                *paths,
            ],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

    def test_valid_files_are_reported_in_deterministic_order(self) -> None:
        (self.root / "z.py").write_text("value = 1\n", encoding="utf-8")
        (self.root / "a.py").write_text("value = 2\n", encoding="utf-8")

        result = self.run_helper("z.py", "a.py")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["CHECKED a.py", "CHECKED z.py"])
        self.assertEqual(result.stderr, "")

    def test_invalid_syntax_fails(self) -> None:
        (self.root / "broken.py").write_text("if True print('no')\n", encoding="utf-8")

        result = self.run_helper("broken.py")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR broken.py:1: syntax error", result.stderr)
        self.assertIn("ERROR no Python files passed syntax checking", result.stderr)

    def test_mixed_inputs_check_valid_file_and_report_every_failure(self) -> None:
        (self.root / "good.py").write_text("answer = 42\n", encoding="utf-8")
        (self.root / "bad.py").write_text("answer =\n", encoding="utf-8")

        result = self.run_helper("missing.py", "bad.py", "good.py")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), ["CHECKED good.py"])
        self.assertIn("ERROR missing.py: cannot resolve", result.stderr)
        self.assertIn("ERROR bad.py:1: syntax error", result.stderr)

    def test_empty_file_list_is_rejected_by_cli(self) -> None:
        result = self.run_helper()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("the following arguments are required: files", result.stderr)

    def test_non_python_file_and_directory_are_rejected(self) -> None:
        (self.root / "notes.txt").write_text("text\n", encoding="utf-8")
        (self.root / "package.py").mkdir()

        result = self.run_helper("notes.txt", "package.py")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR notes.txt: not a .py file", result.stderr)
        self.assertIn("ERROR package.py: not a regular file", result.stderr)

    def test_absolute_path_outside_root_is_rejected(self) -> None:
        outside = Path(self._temporary_directory.name) / "outside.py"
        outside.write_text("value = 1\n", encoding="utf-8")

        result = self.run_helper(str(outside))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("resolved path escapes root", result.stderr)

    def test_symlink_escape_is_rejected(self) -> None:
        outside = Path(self._temporary_directory.name) / "outside.py"
        outside.write_text("value = 1\n", encoding="utf-8")
        (self.root / "escape.py").symlink_to(outside)

        result = self.run_helper("escape.py")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR escape.py: resolved path escapes root", result.stderr)

    def test_symlink_cycle_is_rejected(self) -> None:
        (self.root / "cycle.py").symlink_to("cycle.py")

        result = self.run_helper("cycle.py")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR cycle.py: cannot resolve", result.stderr)

    def test_invalid_encoding_is_rejected(self) -> None:
        (self.root / "encoding.py").write_bytes(
            b"# coding: definitely-not-a-codec\nvalue = 1\n"
        )

        result = self.run_helper("encoding.py")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR encoding.py: cannot read Python source", result.stderr)

    def test_unreadable_file_is_rejected(self) -> None:
        path = self.root / "unreadable.py"
        path.write_text("value = 1\n", encoding="utf-8")
        path.chmod(0)
        self.addCleanup(path.chmod, 0o600)

        result = self.run_helper("unreadable.py")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR unreadable.py: cannot read Python source", result.stderr)

    def test_checked_source_is_never_executed(self) -> None:
        marker = Path(self._temporary_directory.name) / "executed"
        source = self.root / "side_effect.py"
        source.write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('ran', encoding='utf-8')\n",
            encoding="utf-8",
        )

        result = self.run_helper("side_effect.py")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())
        self.assertFalse((self.root / "__pycache__").exists())


if __name__ == "__main__":
    unittest.main()
