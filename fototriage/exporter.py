from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from .models import ImageAnalysis

FOLDERS = {
    "important": "01_importantes",
    "useful": "02_utiles",
    "review": "03_revisar",
    "trash_candidate": "04_basura_probable",
    "corrupt": "05_corruptas",
}


@dataclass
class ExportAction:
    source: Path
    destination: Path
    operation: str


def _unique_destination(
    destination: Path, source: Path, used: set[str]
) -> Path:
    key = str(destination.resolve())
    if key in used:
        return _rename_destination(destination, source, used)
    if destination.exists() and destination.resolve() != source.resolve():
        return _rename_destination(destination, source, used)
    used.add(key)
    return destination


def _rename_destination(destination: Path, source: Path, used: set[str]) -> Path:
    digest = hashlib.sha256(str(source).encode()).hexdigest()[:8]
    while True:
        candidate = destination.with_name(f"{destination.stem}_{digest}{destination.suffix}")
        candidate_key = str(candidate.resolve())
        if candidate_key not in used and not candidate.exists():
            used.add(candidate_key)
            return candidate
        digest = hashlib.sha256(f"{digest}{source}".encode()).hexdigest()[:8]


def build_plan(
    items: list[ImageAnalysis], output: Path, decisions: set[str], operation: str
) -> list[ExportAction]:
    if operation not in {"copy", "move"}:
        raise ValueError("La operacion debe ser copy o move")
    actions: list[ExportAction] = []
    used: set[str] = set()
    for item in items:
        if item.decision not in decisions:
            continue
        source = Path(item.path)
        folder = FOLDERS.get(item.decision, item.decision)
        destination = output / folder / item.relative_path
        destination = _unique_destination(destination, source, used)
        actions.append(ExportAction(source, destination, operation))
    return actions


def execute_plan(actions: list[ExportAction]) -> tuple[int, list[str]]:
    completed = 0
    errors: list[str] = []
    for action in actions:
        try:
            action.destination.parent.mkdir(parents=True, exist_ok=True)
            if action.operation == "copy":
                shutil.copy2(action.source, action.destination)
            else:
                shutil.move(str(action.source), str(action.destination))
            completed += 1
        except Exception as exc:
            errors.append(f"{action.source}: {exc}")
    return completed, errors

