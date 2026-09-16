from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from .analyzers.basic import analyze_basic, enable_heic_if_available, hamming_distance
from .config import config_fingerprint
from .database import Database
from .models import ImageAnalysis
from .scoring import score_image

ProgressCallback = Callable[[int, int, Path], None]


def discover_images(root: Path, formats: list[str]) -> list[Path]:
    allowed = {suffix.lower() for suffix in formats}
    return sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in allowed
    )


def mark_duplicates(items: list[ImageAnalysis], perceptual_distance: int = 4) -> None:
    exact_groups: dict[str, list[ImageAnalysis]] = defaultdict(list)
    for item in items:
        if not item.corrupt and item.sha256:
            exact_groups[item.sha256].append(item)
    for group in exact_groups.values():
        if len(group) < 2:
            continue
        best = max(group, key=lambda x: (x.width * x.height, x.sharpness, x.size_bytes))
        for item in group:
            if item is not best:
                item.duplicate_of = best.path

    # Los hashes de diferencia de imagenes uniformes (por ejemplo una foto
    # completamente negra y otra blanca) pueden coincidir aunque el contenido
    # no sea el mismo. Se excluyen esas imagenes y luego se exige que la
    # relacion de aspecto sea equivalente antes de marcar similitud.
    candidates = [
        i for i in items
        if not i.corrupt and not i.duplicate_of and i.perceptual_hash and i.entropy >= 3.0
    ]
    buckets: dict[str, list[ImageAnalysis]] = defaultdict(list)
    for item in candidates:
        buckets[item.perceptual_hash[:4]].append(item)
    for group in buckets.values():
        if len(group) < 2:
            continue
        ordered = sorted(
            group,
            key=lambda x: (x.width * x.height, x.sharpness, x.size_bytes),
            reverse=True,
        )
        keepers: list[ImageAnalysis] = []
        for item in ordered:
            item_ratio = item.width / max(1, item.height)
            match = next((
                keeper for keeper in keepers
                if abs(item_ratio - (keeper.width / max(1, keeper.height))) <= 0.03
                and hamming_distance(
                    item.perceptual_hash, keeper.perceptual_hash
                ) <= perceptual_distance
            ), None)
            if match:
                item.duplicate_of = match.path
            else:
                keepers.append(item)


def scan(
    source: str | Path,
    database_path: str | Path,
    config: dict,
    profile: str = "fast",
    model_name: str = "yolo11n.pt",
    progress: ProgressCallback | None = None,
) -> tuple[int, list[ImageAnalysis], list[str]]:
    root = Path(source).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"La ruta no es un directorio: {root}")
    enable_heic_if_available()
    paths = discover_images(root, config["formats"])
    warnings: list[str] = []
    detector = None
    if profile in {"balanced", "deep"}:
        try:
            from .analyzers.objects import ObjectDetector

            detector = ObjectDetector(model_name=model_name)
        except Exception as exc:
            warnings.append(str(exc))

    items: list[ImageAnalysis] = []
    for index, path in enumerate(paths, start=1):
        if progress:
            progress(index, len(paths), path)
        item = analyze_basic(path, root)
        if detector is not None and not item.corrupt:
            try:
                item.detections = detector.detect(path)
            except Exception as exc:
                item.reasons.append(f"deteccion de objetos fallo: {exc}")
        items.append(item)

    mark_duplicates(items)
    for item in items:
        preexisting = list(item.reasons)
        score_image(item, config)
        item.reasons = preexisting + item.reasons

    db = Database(database_path)
    try:
        run_id = db.start_run(str(root), profile, config_fingerprint(config))
        for item in items:
            db.save_image(run_id, item)
        db.finish_run(run_id, len(items), sum(1 for item in items if item.corrupt))
    finally:
        db.close()
    return run_id, items, warnings
