from __future__ import annotations

import os
import sys
import threading
from pathlib import Path


VENDOR_DIR = Path(r"C:\WLAppRuntime\vendor_ocr")
CACHE_DIR = Path(r"C:\WLAppRuntime\paddlex_cache")
_ENGINES: dict[str, object] = {}
_RECOGNIZERS: dict[str, object] = {}
_LOCK = threading.Lock()


def is_available() -> bool:
    return (VENDOR_DIR / "paddleocr").is_dir() and CACHE_DIR.is_dir()


def _engine(quality: str = "medium"):
    if quality in _ENGINES:
        return _ENGINES[quality]
    with _LOCK:
        if quality not in _ENGINES:
            os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(CACHE_DIR))
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
            if str(VENDOR_DIR) not in sys.path:
                sys.path.insert(0, str(VENDOR_DIR))
            from paddleocr import PaddleOCR

            tier = "small" if quality == "small" else "medium"
            _ENGINES[quality] = PaddleOCR(
                text_detection_model_name=f"PP-OCRv6_{tier}_det",
                text_recognition_model_name=f"PP-OCRv6_{tier}_rec",
                use_doc_orientation_classify=False,
                # The app already isolates the flat orange label.  UVDoc is
                # useful for curved pages, but on these labels it adds heavy
                # CPU cost and can soften tiny decimal digits.
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
    return _ENGINES[quality]


def read_text(image_path: Path, quality: str = "medium") -> tuple[str, float]:
    results = _engine(quality).predict(input=str(image_path))
    lines: list[str] = []
    scores: list[float] = []
    for result in results:
        payload = result.json
        if callable(payload):
            payload = payload()
        data = payload.get("res", payload) if isinstance(payload, dict) else {}
        texts = data.get("rec_texts", [])
        confidences = data.get("rec_scores", [])
        for index, value in enumerate(texts):
            value = str(value).strip()
            if not value:
                continue
            lines.append(value)
            if index < len(confidences):
                scores.append(float(confidences[index]))
    confidence = sum(scores) / len(scores) if scores else 0.0
    return "\n".join(lines), confidence


def _recognizer(quality: str = "medium"):
    if quality in _RECOGNIZERS:
        return _RECOGNIZERS[quality]
    with _LOCK:
        if quality not in _RECOGNIZERS:
            os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(CACHE_DIR))
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
            if str(VENDOR_DIR) not in sys.path:
                sys.path.insert(0, str(VENDOR_DIR))
            from paddleocr import TextRecognition

            tier = "small" if quality == "small" else "medium"
            _RECOGNIZERS[quality] = TextRecognition(
                model_name=f"PP-OCRv6_{tier}_rec",
            )
    return _RECOGNIZERS[quality]


def read_line_texts(image_paths: list[Path], quality: str = "medium") -> list[tuple[str, float]]:
    """Recognize already isolated text rows without running a detector."""
    if not image_paths:
        return []
    results = _recognizer(quality).predict(input=[str(path) for path in image_paths])
    readings: list[tuple[str, float]] = []
    for result in results:
        payload = result.json
        if callable(payload):
            payload = payload()
        data = payload.get("res", payload) if isinstance(payload, dict) else {}
        readings.append((
            str(data.get("rec_text") or "").strip(),
            float(data.get("rec_score") or 0.0),
        ))
    return readings
