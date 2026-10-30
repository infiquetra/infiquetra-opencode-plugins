"""Consume pinned producer fixtures through the bundled Saga contract seam."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/saga/scripts/outcome_compat.py"
FIXTURES = ROOT / "tests/fixtures/outcome-cross-runtime/v1"


@pytest.fixture
def outcome_compat(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    name = "_opencode_outcome_compat_fixture_consumer"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with monkeypatch.context() as patch:
        # The bundled module inserts its script directory into sys.path at import.
        # Restore both that path and the isolated module entry, including on failure.
        patch.setattr(sys, "path", sys.path.copy())
        patch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        yield module


@pytest.mark.parametrize(
    ("name", "validator"),
    [
        pytest.param(
            "discovery-envelope.json",
            "validate_discovery_envelope",
            id="discovery-envelope.json",
        ),
        pytest.param(
            "canonical-status.json", "validate_canonical_status", id="canonical-status.json"
        ),
        pytest.param(
            "handoff-reference.json", "validate_handoff_reference", id="handoff-reference.json"
        ),
        pytest.param(
            "compatibility-halt.json", "validate_halt_receipt", id="compatibility-halt.json"
        ),
    ],
)
def test_fixture_round_trip(outcome_compat: ModuleType, name: str, validator: str) -> None:
    raw = (FIXTURES / name).read_bytes()
    parsed = outcome_compat.parse_strict_json(raw, what=name)
    validated = getattr(outcome_compat, validator)(parsed)
    assert (outcome_compat.canonical_json(validated) + "\n").encode("utf-8") == raw
    if name == "discovery-envelope.json":
        assert outcome_compat.negotiate(validated["protocol"]) == 1


def test_unknown_field_fixture_halts(outcome_compat: ModuleType) -> None:
    raw = (FIXTURES / "invalid/unknown-field-envelope.json").read_bytes()
    parsed = outcome_compat.parse_strict_json(raw, what="unknown-field fixture")
    with pytest.raises(outcome_compat.CompatibilityHaltError) as exc:
        outcome_compat.validate_discovery_envelope(parsed)
    assert exc.value.code == "schema-field-unknown"


def test_future_protocol_fixture_halts(outcome_compat: ModuleType) -> None:
    raw = (FIXTURES / "invalid/future-protocol-envelope.json").read_bytes()
    parsed = outcome_compat.parse_strict_json(raw, what="future-protocol fixture")
    # A future version is structurally valid; only negotiation should reject it.
    validated = outcome_compat.validate_discovery_envelope(parsed)
    with pytest.raises(outcome_compat.CompatibilityHaltError) as exc:
        outcome_compat.negotiate(validated["protocol"])
    assert exc.value.code == "protocol-version-skew"
