from __future__ import annotations

import json
from pathlib import Path

from fototriage.cli import main
from PIL import Image


def _make_photos(root: Path) -> None:
    Image.effect_noise((1200, 900), 60).convert("RGB").save(root / "foto.jpg")
    Image.new("RGB", (100, 100), "white").save(root / "pequena.png")


def test_cli_scan_report_gallery(tmp_path: Path):
    photos = tmp_path / "fotos"
    photos.mkdir()
    _make_photos(photos)
    db = tmp_path / "cli.sqlite3"
    reports = tmp_path / "reportes"

    code = main(["scan", str(photos), "--db", str(db), "--report", str(reports)])
    assert code == 0
    assert db.exists()
    assert (reports / "resultados.csv").exists()
    assert (reports / "resultados.json").exists()
    assert (reports / "galeria.html").exists()

    code = main(["gallery", "--db", str(db), "--output", str(tmp_path / "galeria.html")])
    assert code == 0
    assert (tmp_path / "galeria.html").exists()


def test_cli_explain_known_and_unknown(tmp_path: Path, capsys):
    import yaml
    from fototriage.config import DEFAULT_CONFIG
    from fototriage.scanner import scan

    photos = tmp_path / "fotos"
    photos.mkdir()
    _make_photos(photos)
    db = tmp_path / "cli.sqlite3"
    scan(photos, db, yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8")), profile="fast")

    code = main(["explain", str(photos / "foto.jpg"), "--db", str(db)])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["relative_path"] == "foto.jpg"

    code = main(["explain", str(photos / "no-existe.jpg"), "--db", str(db)])
    assert code == 2


def test_cli_export_requires_apply(tmp_path: Path):
    photos = tmp_path / "fotos"
    photos.mkdir()
    _make_photos(photos)
    db = tmp_path / "cli.sqlite3"
    assert main(["scan", str(photos), "--db", str(db)]) == 0

    output = tmp_path / "clasificadas"
    code = main(
        [
            "export", "--db", str(db), "--output", str(output),
            "--decision", "important", "--decision", "review", "--mode", "copy",
        ]
    )
    assert code == 0
    assert not output.exists()
