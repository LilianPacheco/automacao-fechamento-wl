from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from wl_fechamento.label_parser import parse_document_text  # noqa: E402
from wl_fechamento.review_service import _apply_message_consensus  # noqa: E402


root = Path(os.environ["APPDATA"]) / "WL Fechamento" / "Capturas"
source = max(root.glob("*/revisao_temporaria.json"), key=lambda path: path.stat().st_mtime)
loaded = json.loads(source.read_text(encoding="utf-8"))
drafts = []
for values in loaded.values():
    for item in values if isinstance(values, list) else []:
        raw_text = str(item.get("ocr_text") or "").strip()
        if raw_text:
            drafts.extend(parse_document_text(
                raw_text,
                message_id=str(item.get("message_id") or ""),
                message_date=str(item.get("message_date") or ""),
                source_path=str(item.get("source_path") or ""),
            ))
_apply_message_consensus(drafts)
pending = [draft for draft in drafts if draft.warnings]
warnings = Counter(warning for draft in drafts for warning in draft.warnings)
print(json.dumps({
    "source": str(source),
    "total": len(drafts),
    "pending": len(pending),
    "automatic": len(drafts) - len(pending),
    "warning_counts": warnings,
}, ensure_ascii=False, indent=2))
