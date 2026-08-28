from __future__ import annotations

import json
import shutil
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wl_fechamento.label_parser import LabelDraft, _majority_explicit_length, parse_document_text
from wl_fechamento.review_service import _apply_message_consensus


captures = Path.home() / "AppData" / "Roaming" / "WL Fechamento" / "Capturas"
source = max(captures.glob("*/revisao_temporaria.json"), key=lambda path: path.stat().st_mtime)
loaded = json.loads(source.read_text(encoding="utf-8"))

if not isinstance(loaded, dict):
    raise SystemExit("Formato de cache não reconhecido.")

updated: dict[str, list[dict]] = {}
drafts_by_key: dict[str, list[LabelDraft]] = {}
for cache_key, values in loaded.items():
    rows: list[LabelDraft] = []
    for item in values if isinstance(values, list) else []:
        if not isinstance(item, dict):
            continue
        # Preserve every field already recognized or corrected, while letting
        # a newer parser fill fields that were previously empty.  Conflicting
        # populated values are never overwritten.
        old = LabelDraft(**item)
        raw_text = old.ocr_text.strip()
        majority_length = _majority_explicit_length(raw_text) if raw_text else ""
        if majority_length:
            old.length = majority_length
        candidates = parse_document_text(
            raw_text,
            message_id=old.message_id,
            message_date=old.message_date,
            source_path=old.source_path,
        ) if raw_text else []
        old_piece = old.piece.strip().upper().replace(" ", "")
        matching = [
            candidate for candidate in candidates
            if old_piece and candidate.piece.strip().upper().replace(" ", "") == old_piece
        ]
        candidate = matching[0] if matching else (candidates[0] if len(candidates) == 1 else None)
        if candidate is not None:
            for field_name in ("work", "product", "piece", "section", "length", "unit_volume"):
                if getattr(old, field_name) in ("", None) and getattr(candidate, field_name) not in ("", None):
                    setattr(old, field_name, getattr(candidate, field_name))
            try:
                old_length = float(old.length.replace(".", "").replace(",", ".")) if old.length else None
                candidate_length = float(candidate.length.replace(".", "").replace(",", ".")) if candidate.length else None
            except ValueError:
                old_length = candidate_length = None
            if all(value is not None for value in (old_length, old.unit_volume, candidate_length, candidate.unit_volume)):
                duplicate_pair = abs(old_length - float(old.unit_volume)) < 0.0005
                swapped_pair = (
                    abs(old_length - float(candidate.unit_volume)) < 0.0005
                    and abs(float(old.unit_volume) - candidate_length) < 0.0005
                )
                candidate_distinct = abs(candidate_length - float(candidate.unit_volume)) >= 0.0005
                if candidate_distinct and (duplicate_pair or swapped_pair):
                    old.length = candidate.length
                    old.unit_volume = candidate.unit_volume
            if (
                "AMPLIACAO FABRIL" in old.work.upper()
                and candidate.work == "UNITERMI - AMPLIACAO FABRIL"
            ):
                old.work = candidate.work
        rows.append(old)
    drafts_by_key[cache_key] = rows

all_drafts = [row for rows in drafts_by_key.values() for row in rows]
_apply_message_consensus(all_drafts)
for cache_key, rows in drafts_by_key.items():
    updated[cache_key] = [asdict(row) for row in rows]

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = source.with_name(f"{source.stem}.before_reparse_{stamp}{source.suffix}")
shutil.copy2(source, backup)
source.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
print(source)
print(f"Backup: {backup}")
