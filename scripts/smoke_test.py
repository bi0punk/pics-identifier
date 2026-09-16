#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image


def main() -> int:
    project = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="fototriage-smoke-") as temp:
        root = Path(temp)
        photos = root / "photos"
        photos.mkdir()
        Image.new("RGB", (1200, 800), "black").save(photos / "negra.jpg")
        Image.effect_noise((1200, 800), 70).convert("RGB").save(photos / "foto.jpg")
        (photos / "copia.jpg").write_bytes((photos / "foto.jpg").read_bytes())
        Image.new("RGB", (100, 100), "white").save(photos / "pequena.png")
        db = root / "result.sqlite3"
        reports = root / "reports"
        result = subprocess.run(
            [sys.executable, "-m", "fototriage.cli", "scan", str(photos),
             "--db", str(db), "--report", str(reports)],
            cwd=project,
            env={"PYTHONPATH": str(project)},
            check=False,
        )
        expected = [
            db,
            reports / "resultados.csv",
            reports / "resultados.json",
            reports / "galeria.html",
        ]
        if result.returncode or not all(path.exists() for path in expected):
            print("Smoke test FALLIDO", file=sys.stderr)
            return 1
        print("Smoke test OK")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
