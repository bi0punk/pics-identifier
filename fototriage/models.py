from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Detection:
    label: str
    confidence: float
    box: list[float] | None = None


@dataclass
class ImageAnalysis:
    path: str
    relative_path: str
    size_bytes: int = 0
    mtime_ns: int = 0
    sha256: str = ""
    perceptual_hash: str = ""
    width: int = 0
    height: int = 0
    format: str = ""
    mode: str = ""
    megapixels: float = 0.0
    brightness: float = 0.0
    sharpness: float = 0.0
    entropy: float = 0.0
    has_exif: bool = False
    camera_make: str = ""
    camera_model: str = ""
    captured_at: str = ""
    has_gps: bool = False
    likely_screenshot: bool = False
    corrupt: bool = False
    error: str = ""
    duplicate_of: str = ""
    detections: list[Detection] = field(default_factory=list)
    score: int = 0
    decision: str = "review"
    components: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    @property
    def filename(self) -> str:
        return Path(self.path).name

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["filename"] = self.filename
        return data

