from __future__ import annotations

from pathlib import Path

from ..models import Detection


class ObjectDetector:
    def __init__(self, model_name: str = "yolo11n.pt", confidence: float = 0.35):
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "Deteccion de objetos no disponible. Instale: pip install -e '.[objects]'"
            ) from exc
        self.model = YOLO(model_name)
        self.confidence = confidence

    def detect(self, path: Path) -> list[Detection]:
        results = self.model.predict(
            source=str(path), conf=self.confidence, verbose=False, device="cpu"
        )
        detections: list[Detection] = []
        for result in results:
            names = result.names
            if result.boxes is None:
                continue
            for box in result.boxes:
                class_id = int(box.cls.item())
                detections.append(
                    Detection(
                        label=str(names[class_id]).lower(),
                        confidence=round(float(box.conf.item()), 4),
                        box=[round(float(v), 1) for v in box.xyxy[0].tolist()],
                    )
                )
        return detections

