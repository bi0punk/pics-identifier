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


def test_scan_incremental_reuses_cached(tmp_path: Path, monkeypatch):
    analyzed: list[str] = []
    real_analyze = __import__("fototriage.scanner", fromlist=["_analyze_fresh"])._analyze_fresh

    def spy(path, root, detector):
        analyzed.append(path.name)
        return real_analyze(path, root, detector)

    monkeypatch.setattr(
        __import__("fototriage.scanner", fromlist=["_analyze_fresh"]), "_analyze_fresh", spy
    )
    db = tmp_path / "scan.sqlite3"
    _photo(tmp_path / "a.jpg")
    _photo(tmp_path / "b.jpg")
    _, _, _ = scan(tmp_path, db, config(), profile="fast", workers=1)
    assert sorted(analyzed) == ["a.jpg", "b.jpg"]

    analyzed.clear()
    _, items, _ = scan(tmp_path, db, config(), profile="fast", workers=1)
    assert analyzed == []
    assert len(items) == 2

    analyzed.clear()
    _photo(tmp_path / "c.jpg")
    _, _, _ = scan(tmp_path, db, config(), profile="fast", workers=1)
    assert analyzed == ["c.jpg"]


def test_scan_invalidates_cache_when_file_changes(tmp_path: Path, monkeypatch):
    from fototriage.scanner import _analyze_fresh

    db = tmp_path / "scan.sqlite3"
    photo = tmp_path / "a.jpg"
    _photo(photo)
    _, _, _ = scan(tmp_path, db, config(), profile="fast", workers=1)

    import time

    time.sleep(0.01)
    _photo(photo, seed=99)
    _, items, _ = scan(tmp_path, db, config(), profile="fast", workers=1)
    assert len(items) == 1
    assert items[0].sha256 == _analyze_fresh(photo, tmp_path, None).sha256
