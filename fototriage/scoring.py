from __future__ import annotations

from collections import Counter
from typing import Any

from .models import ImageAnalysis


VEHICLES = {"car", "motorcycle", "bicycle", "boat", "airplane", "train", "truck", "bus"}
FOOD = {"banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake"}


def _bounded_ratio(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return max(0.0, min(1.0, (value - low) / (high - low)))


def score_image(item: ImageAnalysis, config: dict[str, Any]) -> ImageAnalysis:
    if item.corrupt:
        item.score = 0
        item.decision = "corrupt"
        item.components = {"total": 0}
        item.reasons = [f"archivo no legible: {item.error}"]
        return item

    quality_cfg = config["quality"]
    weights = config["weights"]
    penalties_cfg = config["penalties"]
    reasons: list[str] = []
    penalties = 0.0

    sharp_ratio = _bounded_ratio(
        item.sharpness, float(quality_cfg["blur_bad"]), float(quality_cfg["blur_good"])
    )
    exposure_ok = float(quality_cfg["dark"]) <= item.brightness <= float(quality_cfg["bright"])
    resolution_ratio = min(1.0, item.megapixels / float(quality_cfg["high_megapixels"]))
    quality = float(weights["quality_max"]) * (
        0.55 * sharp_ratio + 0.25 * float(exposure_ok) + 0.20 * resolution_ratio
    )
    if sharp_ratio >= 0.75:
        reasons.append("imagen nitida")
    if not exposure_ok:
        reasons.append("exposicion deficiente")

    metadata = 0.0
    if item.has_exif:
        metadata += 3.0
    if item.camera_make or item.camera_model:
        metadata += 4.0
        reasons.append("metadatos de camara presentes")
    if item.captured_at:
        metadata += 2.0
    if item.has_gps:
        metadata += 1.0
    metadata = min(float(weights["metadata_max"]), metadata)

    label_counts = Counter(d.label for d in item.detections if d.confidence >= 0.35)
    object_weights = config.get("object_weights", {})
    content = 0.0
    for label, count in label_counts.items():
        mapped = "vehicle" if label in VEHICLES else "food" if label in FOOD else label
        weight = float(object_weights.get(label, object_weights.get(mapped, 0)))
        if weight:
            content += weight + min(5.0, max(0, count - 1) * 2.0)
            reasons.append(f"{count} objeto(s) detectado(s): {label}")
    content = min(float(weights["content_max"]), content)

    originality = float(weights["originality"])
    if item.duplicate_of:
        originality = 0.0
        penalties += float(penalties_cfg["duplicate"])
        reasons.append(f"duplicada de {item.duplicate_of}")

    if item.likely_screenshot:
        penalties += float(penalties_cfg["likely_screenshot"])
        reasons.append("posible captura de pantalla")
    if item.sharpness < float(quality_cfg["blur_bad"]):
        penalties += float(penalties_cfg["very_blurry"])
        reasons.append("imagen muy borrosa")
    if item.width < int(quality_cfg["min_width"]) or item.height < int(quality_cfg["min_height"]):
        penalties += float(penalties_cfg["tiny_image"])
        reasons.append("resolucion baja")
    if item.entropy < 2.2:
        penalties += float(penalties_cfg["near_uniform"])
        reasons.append("imagen casi uniforme o vacia")

    base = float(weights["base"])
    total = round(max(0.0, min(100.0, base + quality + metadata + originality + content - penalties)))
    thresholds = config["thresholds"]
    if total >= int(thresholds["important"]):
        decision = "important"
    elif total >= int(thresholds["useful"]):
        decision = "useful"
    elif total >= int(thresholds["review"]):
        decision = "review"
    else:
        decision = "trash_candidate"

    item.score = int(total)
    item.decision = decision
    item.components = {
        "base": round(base, 2),
        "quality": round(quality, 2),
        "metadata": round(metadata, 2),
        "content": round(content, 2),
        "originality": round(originality, 2),
        "penalties": round(penalties, 2),
    }
    item.reasons = reasons or ["sin senales destacadas; requiere revision"]
    return item

