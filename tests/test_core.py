from __future__ import annotations

from pathlib import Path

import yaml
from PIL import Image

from fototriage.analyzers.basic import analyze_basic, hamming_distance
from fototriage.config import DEFAULT_CONFIG
from fototriage.models import Detection
from fototriage.scanner import mark_duplicates
from fototriage.scoring import score_image


def config():
    return yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))


def test_basic_analysis_and_uniform_penalty(tmp_path: Path):
    image_path = tmp_path / "black.jpg"
    Image.new("RGB", (800, 600), (0, 0, 0)).save(image_path)
    item = analyze_basic(image_path, tmp_path)
    score_image(item, config())
    assert not item.corrupt
    assert item.width == 800
    assert item.decision == "trash_candidate"
    assert any("uniforme" in reason for reason in item.reasons)


def test_person_increases_score(tmp_path: Path):
    image_path = tmp_path / "photo.jpg"
    image = Image.effect_noise((1200, 900), 80).convert("RGB")
    image.save(image_path)
    base = analyze_basic(image_path, tmp_path)
    score_image(base, config())
    person = analyze_basic(image_path, tmp_path)
    person.detections = [Detection("person", 0.95)]
    score_image(person, config())
    assert person.score > base.score


def test_exact_duplicate_marks_one(tmp_path: Path):
    first_path = tmp_path / "a.jpg"
    second_path = tmp_path / "b.jpg"
    Image.effect_noise((800, 600), 60).convert("RGB").save(first_path)
    second_path.write_bytes(first_path.read_bytes())
    first = analyze_basic(first_path, tmp_path)
    second = analyze_basic(second_path, tmp_path)
    mark_duplicates([first, second])
    assert bool(first.duplicate_of) != bool(second.duplicate_of)
    assert hamming_distance(first.perceptual_hash, second.perceptual_hash) == 0

