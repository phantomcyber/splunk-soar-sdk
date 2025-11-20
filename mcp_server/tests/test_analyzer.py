import os
from pathlib import Path

from soar_test_assistant.server import find_sdk_root


class TestServer:
    def test_find_sdk_root(self, tmp_path: Path) -> None:
        sdk_dir = tmp_path / "sdk"
        sdk_dir.mkdir()
        (sdk_dir / "src").mkdir()
        (sdk_dir / "src" / "soar_sdk").mkdir()

        test_dir = sdk_dir / "mcp_server" / "tests"
        test_dir.mkdir(parents=True)

        original_cwd = Path.cwd()
        try:
            os.chdir(test_dir)
            result = find_sdk_root()
            assert result == sdk_dir  # noqa: S101
        finally:
            os.chdir(original_cwd)
