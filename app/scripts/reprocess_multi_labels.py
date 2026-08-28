from __future__ import annotations

import json
import os
import shutil
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from PIL import Image

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from wl_fechamento.label_parser import LabelDraft, parse_document_text  # noqa: E402
from wl_fechamento.ocr_service import _orange_label_crops, read_image_texts  # noqa: E402
from wl_fechamento.review_service import _apply_message_consensus  # noqa: E402


root = Path(os.environ["APPDATA"]) / "WL Fechamento" / "Capturas"
cache_path = max(root.glob("*/revisao_temporaria.json"), key=lambda path: path.stat().st_mtime)
loaded = json.loads(cache_path.read_text(encoding="utf-8"))
backup = cache_path.with_name(f"{cache_path.stem}.before_multi_{datetime.now():%Y%m%d_%H%M%S}.json")
shutil.copy2(cache_path, backup)
print(f"BACKUP {backup}", flush=True)

for index, (cache_key, values) in enumerate(list(loaded.items()), start=1):
    if not isinstance(values, list) or not values:
        continue
    first = values[0]
    path = Path(str(first.get("source_path") or ""))
    if not path.exists():
        continue
    with Image.open(path) as image:
        crop_count = len(_orange_label_crops(image))
    if crop_count <= 1:
        continue
    readings = read_image_texts(path)
    new_drafts: list[LabelDraft] = []
    for reading in readings:
        new_drafts.extend(parse_document_text(
            reading.text,
            message_id=str(first.get("message_id") or ""),
            message_date=str(first.get("message_date") or ""),
            source_path=str(path),
        ))
    accepted = (
        len(new_drafts) >= 2
        and all(draft.piece and len(draft.warnings) <= 3 for draft in new_drafts)
    )
    if accepted:
        loaded[cache_key] = [asdict(draft) for draft in new_drafts]
    print(
        f"MULTI {path.name} crops={crop_count} drafts={len(new_drafts)} "
        f"{'OK' if accepted else 'KEPT_OLD'} "
        f"pieces={[draft.piece for draft in new_drafts]}",
        flush=True,
    )
    temporary = cache_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(loaded, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(cache_path)

all_drafts: list[LabelDraft] = []
for values in loaded.values():
    for item in values if isinstance(values, list) else []:
        allowed = LabelDraft.__dataclass_fields__.keys()
        all_drafts.append(LabelDraft(**{key: item.get(key) for key in allowed if key in item}))
_apply_message_consensus(all_drafts)
pending = [draft for draft in all_drafts if draft.warnings]
print("SUMMARY " + json.dumps({
    "total": len(all_drafts),
    "automatic": len(all_drafts) - len(pending),
    "pending": len(pending),
    "pending_percent": round(len(pending) / len(all_drafts) * 100, 1),
    "warnings": Counter(warning for draft in pending for warning in draft.warnings),
}, ensure_ascii=False), flush=True)
