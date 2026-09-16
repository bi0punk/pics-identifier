from __future__ import annotations

from pathlib import Path

import yaml
from fototriage.config import DEFAULT_CONFIG
from fototriage.scanner import discover_images, mark_duplicates, scan
from PIL import Image


def config():
    return yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))


def _photo(path: Path, seed: int = 60):
    Image.effect_noise((1200, 900), seed).convert("RGB").save(path)


def test_discover_images_filters_by_format(tmp_path: Path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.png").write_bytes(b"x")
    (tmp_path / "c.txt").write_bytes(b"x")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "d.webp").write_bytes(b"x")
    found = discover_images(tmp_path, [".jpg", ".png"])
    assert [path.name for path in found] == ["a.jpg", "b.png"]


def test_scan_does_not_stop_on_corrupt(tmp_path: Path):

    _photo(tmp_path / "ok.jpg")
    (tmp_path / "rota.jpg").write_bytes(b"no es una imagen")
    db = tmp_path / "scan.sqlite3"
    run_id, items, warnings = scan(tmp_path, db, config(), profile="fast")
    assert run_id >= 1
    by_name = {Path(item.path).name: item for item in items}
    assert by_name["ok.jpg"].corrupt is False
    assert by_name["rota.jpg"].corrupt is True
    assert any("rota.jpg" in item.error for item in items if item.corrupt)
    assert db.exists()


def test_scan_marks_exact_duplicate(tmp_path: Path):
    _photo(tmp_path / "original.jpg", seed=70)
    (tmp_path / "copia.jpg").write_bytes((tmp_path / "original.jpg").read_bytes())
    db = tmp_path / "scan.sqlite3"
    _, items, _ = scan(tmp_path, db, config(), profile="fast")
    dupes = [item for item in items if item.duplicate_of]
    assert len(dupes) == 1
    keeper = next(item for item in items if not item.duplicate_of)
    assert dupes[0].duplicate_of == keeper.path


def test_mark_duplicates_ignores_uniform_images(tmp_path: Path):
    from fototriage.analyzers.basic import analyze_basic

    black = tmp_path / "negra.jpg"
    white = tmp_path / "blanca.jpg"
    Image.new("RGB", (800, 600), (0, 0, 0)).save(black)
    Image.new("RGB", (800, 600), (255, 255, 255)).save(white)
    first = analyze_basic(black, tmp_path)
    second = analyze_basic(white, tmp_path)
    mark_duplicates([first, second])
    assert not first.duplicate_of
    assert not second.duplicate_of
