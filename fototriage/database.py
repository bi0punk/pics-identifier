from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import Detection, ImageAnalysis

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    profile TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    total INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    sha256 TEXT,
    perceptual_hash TEXT,
    width INTEGER,
    height INTEGER,
    format TEXT,
    mode TEXT,
    megapixels REAL,
    brightness REAL,
    sharpness REAL,
    entropy REAL,
    has_exif INTEGER,
    camera_make TEXT,
    camera_model TEXT,
    captured_at TEXT,
    has_gps INTEGER,
    likely_screenshot INTEGER,
    corrupt INTEGER,
    error TEXT,
    duplicate_of TEXT,
    detections_json TEXT NOT NULL DEFAULT '[]',
    score INTEGER NOT NULL,
    decision TEXT NOT NULL,
    components_json TEXT NOT NULL DEFAULT '{}',
    reasons_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(run_id, path)
);
CREATE INDEX IF NOT EXISTS idx_images_run_decision ON images(run_id, decision);
CREATE INDEX IF NOT EXISTS idx_images_run_score ON images(run_id, score DESC);
CREATE INDEX IF NOT EXISTS idx_images_sha ON images(sha256);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def start_run(self, source: str, profile: str, config_hash: str) -> int:
        cursor = self.connection.execute(
            "INSERT INTO runs(source, profile, config_hash) VALUES (?, ?, ?)",
            (source, profile, config_hash),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def save_image(self, run_id: int, item: ImageAnalysis) -> None:
        self.connection.execute(
            """INSERT OR REPLACE INTO images (
                run_id, path, relative_path, size_bytes, mtime_ns, sha256, perceptual_hash,
                width, height, format, mode, megapixels, brightness, sharpness, entropy,
                has_exif, camera_make, camera_model, captured_at, has_gps,
                likely_screenshot, corrupt, error, duplicate_of, detections_json,
                score, decision, components_json, reasons_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run_id, item.path, item.relative_path, item.size_bytes, item.mtime_ns,
                item.sha256, item.perceptual_hash, item.width, item.height, item.format,
                item.mode, item.megapixels, item.brightness, item.sharpness, item.entropy,
                int(item.has_exif), item.camera_make, item.camera_model, item.captured_at,
                int(item.has_gps), int(item.likely_screenshot), int(item.corrupt),
                item.error, item.duplicate_of,
                json.dumps([d.__dict__ for d in item.detections], ensure_ascii=False),
                item.score, item.decision,
                json.dumps(item.components, ensure_ascii=False),
                json.dumps(item.reasons, ensure_ascii=False),
            ),
        )

    def finish_run(self, run_id: int, total: int, errors: int) -> None:
        self.connection.execute(
            "UPDATE runs SET completed_at=CURRENT_TIMESTAMP,total=?,errors=? WHERE id=?",
            (total, errors, run_id),
        )
        self.connection.commit()

    def latest_run_id(self) -> int:
        row = self.connection.execute(
            "SELECT id FROM runs WHERE completed_at IS NOT NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            raise RuntimeError("La base no contiene ejecuciones. Use primero: fototriage scan RUTA")
        return int(row["id"])

    def load_images(self, run_id: int | None = None) -> list[ImageAnalysis]:
        selected = run_id or self.latest_run_id()
        rows = self.connection.execute(
            "SELECT * FROM images WHERE run_id=? ORDER BY score DESC, relative_path", (selected,)
        ).fetchall()
        items: list[ImageAnalysis] = []
        for row in rows:
            items.append(ImageAnalysis(
                path=row["path"], relative_path=row["relative_path"],
                size_bytes=row["size_bytes"], mtime_ns=row["mtime_ns"], sha256=row["sha256"],
                perceptual_hash=row["perceptual_hash"], width=row["width"], height=row["height"],
                format=row["format"], mode=row["mode"], megapixels=row["megapixels"],
                brightness=row["brightness"], sharpness=row["sharpness"], entropy=row["entropy"],
                has_exif=bool(row["has_exif"]), camera_make=row["camera_make"],
                camera_model=row["camera_model"], captured_at=row["captured_at"],
                has_gps=bool(row["has_gps"]), likely_screenshot=bool(row["likely_screenshot"]),
                corrupt=bool(row["corrupt"]), error=row["error"], duplicate_of=row["duplicate_of"],
                detections=[Detection(**d) for d in json.loads(row["detections_json"])],
                score=row["score"], decision=row["decision"],
                components=json.loads(row["components_json"]),
                reasons=json.loads(row["reasons_json"]),
            ))
        return items

    def run_info(self, run_id: int | None = None) -> dict:
        selected = run_id or self.latest_run_id()
        row = self.connection.execute("SELECT * FROM runs WHERE id=?", (selected,)).fetchone()
        return dict(row) if row else {}
