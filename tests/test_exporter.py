from __future__ import annotations

from pathlib import Path

import pytest
from fototriage.exporter import build_plan, execute_plan
from fototriage.models import ImageAnalysis


def _item(path: Path, decision: str, relative: str = "") -> ImageAnalysis:
    return ImageAnalysis(
        path=str(path),
        relative_path=relative or path.name,
        decision=decision,
        sha256=f"hash-{path.name}",
    )


def test_build_plan_filters_decisions(tmp_path: Path):
    item = _item(tmp_path / "a.jpg", "important")
    plan = build_plan([item], tmp_path / "out", {"review"}, "copy")
    assert plan == []


def test_build_plan_invalid_operation(tmp_path: Path):
    item = _item(tmp_path / "a.jpg", "important")
    with pytest.raises(ValueError):
        build_plan([item], tmp_path / "out", {"important"}, "rename")


def test_build_plan_uses_decision_folder(tmp_path: Path):
    item = _item(tmp_path / "a.jpg", "important")
    plan = build_plan([item], tmp_path / "out", {"important"}, "copy")
    assert len(plan) == 1
    assert plan[0].destination == tmp_path / "out" / "01_importantes" / "a.jpg"


def test_execute_plan_copy_keeps_source(tmp_path: Path):
    source = tmp_path / "foto.jpg"
    source.write_bytes(b"data")
    item = _item(source, "important")
    out = tmp_path / "out"
    plan = build_plan([item], out, {"important"}, "copy")
    completed, errors = execute_plan(plan)
    assert completed == 1
    assert errors == []
    assert (out / "01_importantes" / "foto.jpg").read_bytes() == b"data"
    assert source.exists()


def test_execute_plan_move_removes_source(tmp_path: Path):
    source = tmp_path / "foto.jpg"
    source.write_bytes(b"data")
    item = _item(source, "review")
    out = tmp_path / "out"
    plan = build_plan([item], out, {"review"}, "move")
    completed, errors = execute_plan(plan)
    assert completed == 1
    assert errors == []
    assert (out / "03_revisar" / "foto.jpg").exists()
    assert not source.exists()


def test_dry_run_does_not_write(tmp_path: Path):
    source = tmp_path / "foto.jpg"
    source.write_bytes(b"data")
    item = _item(source, "important")
    out = tmp_path / "out"
    build_plan([item], out, {"important"}, "copy")
    assert not out.exists()


def test_existing_destination_gets_suffix(tmp_path: Path):
    source = tmp_path / "a.jpg"
    source.write_bytes(b"a")
    out = tmp_path / "out"
    existing = out / "01_importantes" / "a.jpg"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"old")
    item = _item(source, "important")
    plan = build_plan([item], out, {"important"}, "copy")
    assert plan[0].destination != existing
    assert plan[0].destination.name != "a.jpg"
