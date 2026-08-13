"""Tests for the symlink-farm installer."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pytest import MonkeyPatch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import install_opencode_plugins as installer


def test_round_trip(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(installer, "REPO_ROOT", Path(__file__).resolve().parent.parent)
    config = tmp_path / "config"
    config.mkdir()

    assert installer.install(config, ["saga"]) == 0
    links = installer.load_state(config)["links"]
    assert len(links) > 0

    for entry in links:
        link = Path(entry["link"])
        assert link.is_symlink()
        assert link.resolve().exists()

    assert installer.status(config) == 0
    assert installer.uninstall(config) == 0
    assert installer.load_state(config)["links"] == []
    assert installer.status(config) == 0


def test_install_never_overwrites_foreign_files(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(installer, "REPO_ROOT", Path(__file__).resolve().parent.parent)
    config = tmp_path / "config"
    (config / "commands").mkdir(parents=True)
    foreign = config / "commands" / "brainstorm.md"
    foreign.write_text("foreign content")

    exit_code = installer.install(config, ["saga"])
    assert exit_code == 1
    assert foreign.read_text() == "foreign content"


def test_uninstall_removes_only_recorded_links(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(installer, "REPO_ROOT", Path(__file__).resolve().parent.parent)
    config = tmp_path / "config"
    (config / "commands").mkdir(parents=True)
    foreign = config / "commands" / "mine.md"
    foreign.write_text("mine")

    assert installer.install(config, ["saga"]) == 0
    assert installer.uninstall(config) == 0
    assert foreign.exists()


def test_install_resyncs_missing_state_file(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(installer, "REPO_ROOT", Path(__file__).resolve().parent.parent)
    config = tmp_path / "config"
    config.mkdir()

    # First install
    assert installer.install(config, ["saga"]) == 0
    state_file = config / ".infiquetra-plugins.json"
    assert state_file.exists()

    # Remove state file while leaving symlinks on disk
    state_file.unlink()
    assert installer.load_state(config)["links"] == []

    # Reinstall should re-record existing links in state
    assert installer.install(config, ["saga"]) == 0
    reloaded = installer.load_state(config)["links"]
    assert len(reloaded) > 0


def test_status_detects_broken_symlinks(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(installer, "REPO_ROOT", Path(__file__).resolve().parent.parent)
    config = tmp_path / "config"
    config.mkdir()

    assert installer.install(config, ["saga"]) == 0

    # Create a broken symlink and record in state
    broken_link = config / "commands" / "dangling.md"
    broken_link.symlink_to(tmp_path / "nonexistent.md")
    state = installer.load_state(config)
    state["links"].append({"link": str(broken_link), "target": str(tmp_path / "nonexistent.md")})
    installer.save_state(config, state)

    assert installer.status(config) == 0
    out = capsys.readouterr().out
    assert "BROKEN" in out
    assert "dangling.md" in out

