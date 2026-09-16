from __future__ import annotations

import itertools
import os
import threading
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .analyzers.basic import analyze_basic, enable_heic_if_available, hamming_distance
from .config import config_fingerprint
from .database import Database
from .models import Detection, ImageAnalysis
from .scoring import score_image

ProgressCallback = Callable[[int, int, Path], None]

# YOLO no es seguro para inferencia concurrente sobre la misma instancia.
_DETECTOR_LOCK = threading.Lock()


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


def _analyze_fresh(
    path: Path, root: Path, detector
) -> ImageAnalysis:
    item = analyze_basic(path, root)
    if detector is not None and not item.corrupt:
        try:
            with _DETECTOR_LOCK:
                item.detections = detector.detect(path)
        except Exception as exc:
            item.reasons.append(f"deteccion de objetos fallo: {exc}")
    return item


def _reuse_from_cache(
    cache: dict[str, ImageAnalysis], path: Path, root: Path
) -> ImageAnalysis | None:
    cached = cache.get(path.relative_to(root).as_posix())
    if cached is None:
        return None
    stat = path.stat()
    if cached.size_bytes != stat.st_size or cached.mtime_ns != stat.st_mtime_ns:
        return None
    fresh = ImageAnalysis(
        path=cached.path,
        relative_path=cached.relative_path,
        size_bytes=cached.size_bytes,
        mtime_ns=cached.mtime_ns,
        sha256=cached.sha256,
        perceptual_hash=cached.perceptual_hash,
        width=cached.width,
        height=cached.height,
        format=cached.format,
        mode=cached.mode,
        megapixels=cached.megapixels,
        brightness=cached.brightness,
        sharpness=cached.sharpness,
        entropy=cached.entropy,
        has_exif=cached.has_exif,
        camera_make=cached.camera_make,
        camera_model=cached.camera_model,
        captured_at=cached.captured_at,
        has_gps=cached.has_gps,
        likely_screenshot=cached.likely_screenshot,
        corrupt=cached.corrupt,
        error=cached.error,
        detections=[Detection(d.label, d.confidence, d.box) for d in cached.detections],
    )
    return fresh


def _analyze_paths(
    paths: list[Path],
    root: Path,
    detector,
    cache: dict[str, ImageAnalysis],
    progress: ProgressCallback | None,
    workers: int | None,
) -> list[ImageAnalysis]:
    def analyze(path: Path) -> ImageAnalysis:
        reused = _reuse_from_cache(cache, path, root)
        return reused if reused is not None else _analyze_fresh(path, root, detector)

    workers = workers if workers and workers > 0 else min(32, (os.cpu_count() or 1) + 4)
    if workers == 1:
        items: list[ImageAnalysis] = []
        for index, path in enumerate(paths, start=1):
            if progress:
                progress(index, len(paths), path)
            items.append(analyze(path))
        return items
    ordered: list[ImageAnalysis] = [None] * len(paths)  # type: ignore[list-item]
    completed = itertools.count(1)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(analyze, path): index for index, path in enumerate(paths)
        }
        for future in as_completed(futures):
            index = futures[future]
            ordered[index] = future.result()
            if progress:
                progress(next(completed), len(paths), paths[index])
    return [item for item in ordered if item is not None]


def _load_cache(
    database_path: str | Path, root: Path, profile: str, config: dict
) -> dict[str, ImageAnalysis]:
    db: Database | None = None
    try:
        db = Database(database_path)
        run_id = db.latest_run_id()
        info = db.run_info(run_id)
        if not info:
            return {}
        if (
            info.get("source") != str(root)
            or info.get("profile") != profile
            or info.get("config_hash") != config_fingerprint(config)
        ):
            return {}
        return {item.relative_path: item for item in db.load_images(run_id)}
    except Exception:
        return {}
    finally:
        if db is not None:
            db.close()


def scan(
    source: str | Path,
    database_path: str | Path,
    config: dict,
    profile: str = "fast",
    model_name: str = "yolo11n.pt",
    progress: ProgressCallback | None = None,
    workers: int | None = None,
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

    cache = _load_cache(database_path, root, profile, config)
    items = _analyze_paths(paths, root, detector, cache, progress, workers)

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
