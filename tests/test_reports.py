from __future__ import annotations

import json
from pathlib import Path

from fototriage.models import ImageAnalysis
from fototriage.reports import write_all
from PIL import Image


def _item(path: Path) -> ImageAnalysis:
    return ImageAnalysis(
        path=str(path),
        relative_path=path.name,
        size_bytes=10,
        mtime_ns=0,
        sha256="ab" * 16,
        perceptual_hash="cd" * 16,
        width=800,
        height=600,
        megapixels=0.48,
        brightness=120.0,
        sharpness=50.0,
        entropy=7.0,
        score=80,
        decision="important",
        reasons=["nitida"],
    )


def test_write_all_generates_three_reports(tmp_path: Path):
    photo = tmp_path / "foto.jpg"
    Image.effect_noise((800, 600), 60).convert("RGB").save(photo)
    output = tmp_path / "out"
    paths = write_all([_item(photo)], output, {"id": 1, "source": "/fotos"})
    assert all(path.exists() for path in paths)

    payload = json.loads(paths[1].read_text(encoding="utf-8"))
    assert payload["run"]["id"] == 1
    assert payload["summary"]["total"] == 1
    assert payload["images"][0]["decision"] == "important"

    csv_text = paths[0].read_text(encoding="utf-8")
    assert "path" in csv_text
    assert "foto.jpg" in csv_text

    html = paths[2].read_text(encoding="utf-8")
    assert "FotoTriage" in html
    assert 'data-decision="important"' in html


def test_summary_empty_list_is_zero():
    from fototriage.reports import summary

    assert summary([])["total"] == 0
    assert summary([])["average_score"] == 0
