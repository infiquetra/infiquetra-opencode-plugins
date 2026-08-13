"""Tests for the symlink-farm installer."""

from __future__ import annotations

import sys
from pathlib import Path

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

