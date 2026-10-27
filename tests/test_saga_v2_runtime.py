"""Exercise the bridge against an isolated OpenCode 2 server without an LLM."""

import base64
import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "plugins/saga/opencode/saga-hooks.ts"


def wait_for(check: Any, timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while not check():
        if time.monotonic() >= deadline:
            raise AssertionError("timed out waiting for the local OpenCode server")
        time.sleep(0.05)


def test_offline_v2_session_hooks(tmp_path: Path) -> None:
    opencode = os.environ.get("OPENCODE_V2_BIN") or shutil.which("opencode")
    if not opencode:
        pytest.skip("OpenCode 2 is not installed")
    version = subprocess.run([opencode, "--version"], capture_output=True, text=True, timeout=15)
    if not re.search(r"(?:^|\s)v?2\.", version.stdout):
        pytest.skip("OpenCode 2 is not installed")

    home = tmp_path / "home"
    plugin = tmp_path / "saga"
    (plugin / "opencode").mkdir(parents=True)
    (plugin / "hooks").mkdir()
    shutil.copy(BRIDGE, plugin / "opencode/saga-hooks.ts")
    hooks = {
        "SessionStart": [{"hooks": [{"command": 'echo start >> "$SAGA_TEST_MARKER"'}]}],
        "SessionEnd": [{"hooks": [{"command": 'echo end >> "$SAGA_TEST_MARKER"'}]}],
    }
    (plugin / "hooks/hooks.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
    plugin_dir = home / ".config/opencode/plugins"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "saga-hooks.ts").symlink_to(plugin / "opencode/saga-hooks.ts")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    marker = tmp_path / "events"
    shell_marker = tmp_path / "shell"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    env = {
        "HOME": str(home),
        "PATH": os.environ["PATH"],
        "OPENCODE_SERVER_PASSWORD": "isolated-test-password",
        "SAGA_TEST_MARKER": str(marker),
        "SAGA_TEST_SHELL": str(shell_marker),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_STATE_HOME": str(home / ".local/state"),
    }
    server = subprocess.Popen(
        [opencode, "serve", "--hostname", "127.0.0.1", "--port", str(port)],
        cwd=workspace,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    token = base64.b64encode(b"opencode:isolated-test-password").decode()

    def request(path: str, payload: dict[str, object] | None = None, method: str = "GET") -> Any:
        body = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(
            base + path,
            data=body,
            headers={"Authorization": "Basic " + token, "Content-Type": "application/json"},
            method=method,
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read()
            return json.loads(data) if data else None

    def ready() -> bool:
        if server.poll() is not None:
            raise AssertionError("local OpenCode server exited")
        try:
            request("/api/info")
            return True
        except (urllib.error.URLError, TimeoutError):
            return False

    def events() -> list[str]:
        return marker.read_text(encoding="utf-8").splitlines() if marker.exists() else []

    try:
        wait_for(ready)
        session = request(
            "/api/session", {"title": "offline test", "directory": str(workspace)}, "POST"
        )
        session_id = session["data"]["id"]
        prompt = {"text": "offline test", "resume": False}
        request(f"/api/session/{session_id}/prompt", prompt, "POST")
        request(f"/api/session/{session_id}/prompt", prompt, "POST")
        wait_for(lambda: "start" in events())
        assert events().count("start") == 1
        request(
            f"/api/session/{session_id}/shell",
            {"command": 'printf %s "$SAGA_PLUGIN_ROOT" > "$SAGA_TEST_SHELL"'},
            "POST",
        )
        wait_for(shell_marker.exists)
        assert shell_marker.read_text(encoding="utf-8") == str(plugin.resolve())
        request(f"/api/session/{session_id}", method="DELETE")
        wait_for(lambda: "end" in events())
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
