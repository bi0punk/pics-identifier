from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError

from ..models import ImageAnalysis


def enable_heic_if_available() -> bool:
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
        return True
    except ImportError:
        return False


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def difference_hash(image: Image.Image, hash_size: int = 8) -> str:
    gray = ImageOps.grayscale(image).resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    pixels = np.asarray(gray, dtype=np.int16)
    bits = pixels[:, 1:] > pixels[:, :-1]
    value = 0
    for bit in bits.flatten():
        value = (value << 1) | int(bit)
    return f"{value:0{hash_size * hash_size // 4}x}"


def hamming_distance(left: str, right: str) -> int:
    if not left or not right or len(left) != len(right):
        return 999
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _entropy(gray: np.ndarray) -> float:
    histogram = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    probabilities = histogram[histogram > 0] / gray.size
    return float(-np.sum(probabilities * np.log2(probabilities)))


def _sharpness(gray: np.ndarray) -> float:
    sample = gray.astype(np.float32)
    gx = np.diff(sample, axis=1)
    gy = np.diff(sample, axis=0)
    return float((np.var(gx) + np.var(gy)) / 2.0)


def _exif_fields(image: Image.Image) -> dict[str, Any]:
    try:
        exif = image.getexif()
    except Exception:
        return {}
    if not exif:
        return {}
    named = {ExifTags.TAGS.get(key, str(key)): value for key, value in exif.items()}
    return named


def _likely_screenshot(path: Path, width: int, height: int, has_exif: bool) -> bool:
    name = path.name.lower()
    explicit = any(token in name for token in ("screenshot", "captura", "screen_shot"))
    if explicit:
        return True
    if has_exif or path.suffix.lower() not in {".png", ".webp"}:
        return False
    ratio = max(width, height) / max(1, min(width, height))
    common_screen_size = (width, height) in {
        (1080, 1920), (1080, 2400), (1080, 2340), (720, 1280),
        (1366, 768), (1920, 1080), (1440, 900), (2560, 1440),
    }
    return common_screen_size or ratio >= 1.75


def analyze_basic(path: Path, root: Path) -> ImageAnalysis:
    stat = path.stat()
    item = ImageAnalysis(
        path=str(path.resolve()),
        relative_path=str(path.resolve().relative_to(root.resolve())),
        size_bytes=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
    )
    try:
        item.sha256 = sha256_file(path)
        with Image.open(path) as opened:
            opened.load()
            image = ImageOps.exif_transpose(opened)
            item.width, item.height = image.size
            item.format = opened.format or path.suffix.lstrip(".").upper()
            item.mode = image.mode
            item.megapixels = round((item.width * item.height) / 1_000_000, 3)
            exif = _exif_fields(opened)
            item.has_exif = bool(exif)
            item.camera_make = str(exif.get("Make", "")).strip()
            item.camera_model = str(exif.get("Model", "")).strip()
            item.captured_at = str(exif.get("DateTimeOriginal", exif.get("DateTime", ""))).strip()
            item.has_gps = bool(exif.get("GPSInfo"))
            preview = ImageOps.grayscale(image).copy()
            preview.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            gray = np.asarray(preview, dtype=np.uint8)
            item.brightness = round(float(np.mean(gray)), 2)
            item.sharpness = round(_sharpness(gray), 2)
            item.entropy = round(_entropy(gray), 3)
            item.perceptual_hash = difference_hash(image)
            item.likely_screenshot = _likely_screenshot(
                path, item.width, item.height, item.has_exif
            )
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        item.corrupt = True
        item.error = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        item.corrupt = True
        item.error = f"Error inesperado {type(exc).__name__}: {exc}"
    return item
