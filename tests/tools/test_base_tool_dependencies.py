from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.base_tool import BaseTool, DependencyError, ToolResult


class DummyTool(BaseTool):
    def execute(self, inputs: dict) -> ToolResult:
        return ToolResult(success=True)


class BinaryDependencyTests(unittest.TestCase):
    def test_binary_dependency_prefix_is_checked_like_cmd(self) -> None:
        tool = DummyTool()
        tool.dependencies = ["binary:definitely-not-installed-openmontage-test"]
        tool.install_instructions = "install it"

        with patch("tools.base_tool.shutil.which", return_value=None):
            with self.assertRaises(DependencyError):
                tool.check_dependencies()

    def test_binary_dependency_prefix_accepts_available_command(self) -> None:
        tool = DummyTool()
        tool.dependencies = ["binary:ffmpeg"]
        tool.install_instructions = "install ffmpeg"

        with patch("tools.base_tool.shutil.which", return_value="/usr/bin/ffmpeg"):
            tool.check_dependencies()
    def test_run_command_error_includes_stderr(self) -> None:
        tool = DummyTool()

        with self.assertRaisesRegex(RuntimeError, "specific stderr"):
            tool.run_command([
                sys.executable,
                "-c",
                "import sys; print('specific stderr', file=sys.stderr); sys.exit(7)",
            ])


if __name__ == "__main__":
    unittest.main()
