from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PIL import Image

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from wl_fechamento.ocr_service import _orange_label_crops  # noqa: E402

root = Path(os.environ["APPDATA"]) / "WL Fechamento" / "Capturas"
source = max(root.glob("*/revisao_temporaria.json"), key=lambda path: path.stat().st_mtime)
loaded = json.loads(source.read_text(encoding="utf-8"))
counts: list[tuple[str, int]] = []
for values in loaded.values():
    if not isinstance(values, list) or not values:
        continue
    path = Path(str(values[0].get("source_path") or ""))
    if not path.exists():
        continue
    with Image.open(path) as image:
        count = len(_orange_label_crops(image))
    if count > 1:
        counts.append((str(path), count))
        print(count, path.name)
print(f"MULTI_PHOTOS={len(counts)} EXTRA_LABELS={sum(count - 1 for _, count in counts)}")
