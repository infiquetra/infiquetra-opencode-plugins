"""Exercise the Saga bridge with isolated homes and no model credentials."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "plugins/saga/opencode/saga-hooks.ts"


def test_v1_and_v2_hook_mappings(tmp_path: Path) -> None:
    bun = shutil.which("bun")
    if bun is None:
        pytest.skip("Bun is needed to load the OpenCode TypeScript bridge")
    plugin = tmp_path / "saga"
    (plugin / "opencode").mkdir(parents=True)
    (plugin / "hooks").mkdir()
    shutil.copy(BRIDGE, plugin / "opencode/saga-hooks.ts")
    hooks = {
        "SessionStart": [{"hooks": [{"command": 'echo start >> "$SAGA_TEST_MARKER"'}]}],
        "PreToolUse": [{"matcher": "Bash", "hooks": [{"command": "echo denied >&2; exit 2"}]}],
        "PostToolUse": [
            {"matcher": "Bash", "hooks": [{"command": 'echo post >> "$SAGA_TEST_MARKER"'}]}
        ],
        "PreCompact": [{"hooks": [{"command": 'echo compact >> "$SAGA_TEST_MARKER"'}]}],
    }
    (plugin / "hooks/hooks.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
    env = {
        "HOME": str(tmp_path),
        "PATH": os.environ["PATH"],
        "SAGA_TEST_ROOT": str(plugin),
        "SAGA_TEST_MARKER": str(tmp_path / "events"),
    }
    result = subprocess.run(
        [bun, str(ROOT / "tests/saga-hooks-driver.ts"), str(plugin / "opencode/saga-hooks.ts")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
