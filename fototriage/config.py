from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "scoring.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path).expanduser().resolve() if path else DEFAULT_CONFIG
    if not target.is_file():
        raise FileNotFoundError(f"No existe el archivo de configuracion: {target}")
    with target.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    required = {"thresholds", "quality", "weights", "penalties", "formats"}
    missing = required.difference(config)
    if missing:
        raise ValueError(f"Configuracion incompleta; faltan: {', '.join(sorted(missing))}")
    return config


def config_fingerprint(config: dict[str, Any]) -> str:
    raw = json.dumps(config, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]

