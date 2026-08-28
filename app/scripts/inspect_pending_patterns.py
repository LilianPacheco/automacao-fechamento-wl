from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from wl_fechamento.label_parser import parse_document_text  # noqa: E402


root = Path(os.environ["APPDATA"]) / "WL Fechamento" / "Capturas"
source = max(root.glob("*/revisao_temporaria.json"), key=lambda path: path.stat().st_mtime)
loaded = json.loads(source.read_text(encoding="utf-8"))
index = 0
for values in loaded.values():
    for item in values if isinstance(values, list) else []:
        raw = str(item.get("ocr_text") or "")
        if not raw:
            continue
        for draft in parse_document_text(
            raw,
            message_id=str(item.get("message_id") or ""),
            message_date=str(item.get("message_date") or ""),
            source_path=str(item.get("source_path") or ""),
        ):
            if not draft.warnings:
                continue
            index += 1
            print(json.dumps({
                "index": index,
                "warnings": draft.warnings,
                "work": draft.work,
                "product": draft.product,
                "piece": draft.piece,
                "section": draft.section,
                "length": draft.length,
                "unit_volume": draft.unit_volume,
                "raw": draft.ocr_text.replace("\n", " | ")[:700],
                "source": draft.source_path,
            }, ensure_ascii=False))
