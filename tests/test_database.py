from __future__ import annotations

from pathlib import Path

from fototriage.database import Database
from fototriage.models import Detection, ImageAnalysis


def _sample() -> ImageAnalysis:
    return ImageAnalysis(
        path="/fotos/sub/a.jpg",
        relative_path="sub/a.jpg",
        size_bytes=1024,
        mtime_ns=1000,
        sha256="deadbeef" * 4,
        perceptual_hash="cafebabe" * 4,
        width=800,
        height=600,
        format="JPEG",
        mode="RGB",
        megapixels=0.48,
        brightness=120.0,
        sharpness=55.0,
        entropy=7.0,
        has_exif=True,
        camera_make="Test",
        camera_model="Cam 1",
        captured_at="2024:01:01 12:00:00",
        has_gps=True,
        detections=[Detection("person", 0.95)],
        score=85,
        decision="important",
        components={"calidad": 20.0},
        reasons=["nitida"],
    )


def test_database_round_trip(tmp_path: Path):
    db = Database(tmp_path / "test.sqlite3")
    try:
        run_id = db.start_run("/fotos", "fast", "hash123")
        db.save_image(run_id, _sample())
        db.finish_run(run_id, 1, 0)

        loaded = db.load_images(run_id)
        assert len(loaded) == 1
        item = loaded[0]
        assert item.path == "/fotos/sub/a.jpg"
        assert item.relative_path == "sub/a.jpg"
        assert item.score == 85
        assert item.decision == "important"
        assert item.sha256 == "deadbeef" * 4
        assert item.has_exif and item.has_gps
        assert item.detections[0].label == "person"
        assert item.detections[0].confidence == 0.95
        assert item.components == {"calidad": 20.0}
        assert item.reasons == ["nitida"]

        assert db.latest_run_id() == run_id
        assert db.run_info(run_id)["source"] == "/fotos"
        assert db.run_info(run_id)["total"] == 1
    finally:
        db.close()


def test_incomplete_run_is_not_latest(tmp_path: Path):
    db = Database(tmp_path / "test.sqlite3")
    try:
        first = db.start_run("/a", "fast", "h1")
        db.finish_run(first, 0, 0)
        second = db.start_run("/b", "fast", "h2")
        assert db.latest_run_id() == first
        db.finish_run(second, 0, 0)
        assert db.latest_run_id() == second
    finally:
        db.close()


def test_load_images_orders_by_score(tmp_path: Path):
    db = Database(tmp_path / "test.sqlite3")
    try:
        run_id = db.start_run("/fotos", "fast", "hash")
        low = _sample()
        low.path = "/fotos/low.jpg"
        low.relative_path = "low.jpg"
        low.score = 10
        high = _sample()
        high.path = "/fotos/high.jpg"
        high.relative_path = "high.jpg"
        high.score = 90
        db.save_image(run_id, low)
        db.save_image(run_id, high)
        db.finish_run(run_id, 2, 0)
        items = db.load_images(run_id)
        assert [item.score for item in items] == [90, 10]
    finally:
        db.close()
