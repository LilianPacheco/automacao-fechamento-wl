from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from wl_fechamento.label_parser import parse_document_text  # noqa: E402
from wl_fechamento.review_service import _apply_message_consensus  # noqa: E402

root = Path(os.environ["APPDATA"]) / "WL Fechamento" / "Capturas"
source = max(root.glob("*/revisao_temporaria.json"), key=lambda path: path.stat().st_mtime)
loaded = json.loads(source.read_text(encoding="utf-8"))
drafts = []
for values in loaded.values():
    for item in values if isinstance(values, list) else []:
        raw = str(item.get("ocr_text") or "").strip()
        if raw:
            drafts.extend(parse_document_text(
                raw,
                message_id=str(item.get("message_id") or ""),
                message_date=str(item.get("message_date") or ""),
                source_path=str(item.get("source_path") or ""),
            ))
_apply_message_consensus(drafts)
pending = [draft for draft in drafts if draft.warnings]
print("COMBINATIONS")
for warnings, count in Counter(tuple(draft.warnings) for draft in pending).most_common():
    print(count, " | ".join(warnings))
print("ROWS")
for index, draft in enumerate(pending, 1):
    print(json.dumps({
        "i": index,
        "warnings": draft.warnings,
        "date": draft.message_date,
        "work": draft.work,
        "product": draft.product,
        "piece": draft.piece,
        "section": draft.section,
        "length": draft.length,
        "volume": draft.unit_volume,
        "file": Path(draft.source_path).name,
    }, ensure_ascii=False))
