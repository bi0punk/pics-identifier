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


def build_plan(
    items: list[ImageAnalysis], output: Path, decisions: set[str], operation: str
) -> list[ExportAction]:
    if operation not in {"copy", "move"}:
        raise ValueError("La operacion debe ser copy o move")
    actions: list[ExportAction] = []
    for item in items:
        if item.decision not in decisions:
            continue
        source = Path(item.path)
        folder = FOLDERS.get(item.decision, item.decision)
        destination = output / folder / item.relative_path
        if destination.exists() and destination.resolve() != source.resolve():
            suffix = hashlib.sha256(str(source).encode()).hexdigest()[:8]
            destination = destination.with_name(f"{destination.stem}_{suffix}{destination.suffix}")
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

