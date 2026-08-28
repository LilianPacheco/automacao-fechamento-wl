from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from wl_fechamento.label_parser import LabelDraft, normalize_type, parse_document_text  # noqa: E402
from wl_fechamento.ocr_service import read_image_text_targeted  # noqa: E402
from wl_fechamento.review_service import _apply_message_consensus  # noqa: E402


def latest_cache() -> Path:
    root = Path(os.environ["APPDATA"]) / "WL Fechamento" / "Capturas"
    candidates = sorted(
        root.glob("*/revisao_temporaria.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise SystemExit("Nenhum cache de revisão foi encontrado.")
    return candidates[0]


def write_cache(path: Path, groups: dict[str, list[LabelDraft]]) -> None:
    payload = {
        cache_key: [asdict(draft) for draft in drafts]
        for cache_key, drafts in groups.items()
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def load_groups(path: Path) -> dict[str, list[LabelDraft]]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise SystemExit("Formato de cache não reconhecido.")
    groups: dict[str, list[LabelDraft]] = {}
    for cache_key, values in loaded.items():
        drafts = []
        for item in values if isinstance(values, list) else []:
            if not isinstance(item, dict):
                continue
            allowed = LabelDraft.__dataclass_fields__.keys()
            drafts.append(LabelDraft(**{key: item.get(key) for key in allowed if key in item}))
        groups[cache_key] = drafts
    return groups


def _refresh(draft: LabelDraft) -> None:
    try:
        length = float(draft.length.replace(".", "").replace(",", ".")) if draft.length else None
    except ValueError:
        length = None
    if (
        length is not None
        and draft.unit_volume is not None
        and abs(length - float(draft.unit_volume)) < 0.0005
    ):
        draft.unit_volume = None
        if "Confirmar volume unitário" not in draft.warnings:
            draft.warnings.append("Confirmar volume unitário")
    draft.type_name = normalize_type(draft.work, draft.product, length) if draft.product else ""
    draft.dimensions = " ".join(value for value in (draft.section, draft.length) if value)
    resolved = {
        "Confirmar obra": bool(draft.work),
        "Confirmar produto": bool(draft.product),
        "Confirmar peça": bool(draft.piece),
        "Confirmar seção": bool(draft.section),
        "Confirmar comprimento": bool(draft.length),
        "Confirmar volume unitário": draft.unit_volume is not None,
        "Confirmar tipo normalizado": bool(draft.type_name),
    }
    draft.warnings = [warning for warning in draft.warnings if not resolved.get(warning, False)]
    draft.status = "PRONTO PARA REVISÃO" if not draft.warnings else "CONFIRMAR"


def merge_complementary(old_drafts: list[LabelDraft], new_drafts: list[LabelDraft]) -> list[LabelDraft]:
    """Fill missing fields from another OCR pass without overwriting conflicts."""
    merged = [LabelDraft(**asdict(draft)) for draft in old_drafts]
    used: set[int] = set()
    for old in merged:
        try:
            old_length_value = float(old.length.replace(".", "").replace(",", ".")) if old.length else None
        except ValueError:
            old_length_value = None
        invalid_duplicate_volume = (
            old.unit_volume is not None
            and old_length_value is not None
            and abs(float(old.unit_volume) - old_length_value) < 0.0005
        )
        if invalid_duplicate_volume:
            old.unit_volume = None
            if "Confirmar volume unitário" not in old.warnings:
                old.warnings.append("Confirmar volume unitário")
        old_piece = old.piece.strip().upper().replace(" ", "")
        candidates = [
            (index, draft)
            for index, draft in enumerate(new_drafts)
            if index not in used
            and (
                (old_piece and draft.piece.strip().upper().replace(" ", "") == old_piece)
                or (len(merged) == len(new_drafts) == 1)
            )
        ]
        if not candidates:
            continue
        index, new = candidates[0]
        used.add(index)
        for field_name in ("work", "product", "piece", "section", "length", "unit_volume"):
            if getattr(old, field_name) in ("", None) and getattr(new, field_name) not in ("", None):
                setattr(old, field_name, getattr(new, field_name))
        try:
            current_length = float(old.length.replace(".", "").replace(",", ".")) if old.length else None
            candidate_length = float(new.length.replace(".", "").replace(",", ".")) if new.length else None
        except ValueError:
            current_length = candidate_length = None
        if all(value is not None for value in (current_length, old.unit_volume, candidate_length, new.unit_volume)):
            duplicate_pair = abs(current_length - float(old.unit_volume)) < 0.0005
            swapped_pair = (
                abs(current_length - float(new.unit_volume)) < 0.0005
                and abs(float(old.unit_volume) - candidate_length) < 0.0005
            )
            candidate_distinct = abs(candidate_length - float(new.unit_volume)) >= 0.0005
            if candidate_distinct and (duplicate_pair or swapped_pair):
                old.length = new.length
                old.unit_volume = new.unit_volume
        if (
            "AMPLIACAO FABRIL" in old.work.upper()
            and new.work == "UNITERMI - AMPLIACAO FABRIL"
        ):
            old.work = new.work
        old.ocr_text = "\n".join(
            dict.fromkeys(part for part in (old.ocr_text.strip(), new.ocr_text.strip()) if part)
        )
        old.warnings = list(dict.fromkeys([*old.warnings, *new.warnings]))
        _refresh(old)
    # Keep genuinely new, separately identified labels from multi-label photos.
    for index, draft in enumerate(new_drafts):
        if index not in used and draft.piece and all(
            draft.piece.strip().upper().replace(" ", "") != old.piece.strip().upper().replace(" ", "")
            for old in merged if old.piece
        ):
            merged.append(draft)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument(
        "--contains",
        action="append",
        default=[],
        help="Process only source paths containing this text (repeatable).",
    )
    args = parser.parse_args()

    cache_path = latest_cache()
    groups = load_groups(cache_path)
    # Always compare against the current parser, not stale warning lists saved
    # by an older app version.
    for cache_key, old_drafts in list(groups.items()):
        reparsed: list[LabelDraft] = []
        for draft in old_drafts:
            if draft.ocr_text.strip():
                reparsed.extend(parse_document_text(
                    draft.ocr_text,
                    message_id=draft.message_id,
                    message_date=draft.message_date,
                    source_path=draft.source_path,
                ))
            else:
                reparsed.append(draft)
        groups[cache_key] = merge_complementary(old_drafts, reparsed)
    _apply_message_consensus([draft for values in groups.values() for draft in values])
    pending_keys = [
        cache_key
        for cache_key, drafts in groups.items()
        if any(draft.warnings for draft in drafts)
    ]
    if args.contains:
        needles = [value.casefold() for value in args.contains if value.strip()]
        pending_keys = [
            cache_key for cache_key in pending_keys
            if any(
                any(needle in draft.source_path.casefold() for needle in needles)
                for draft in groups[cache_key]
            )
        ]
    if args.limit > 0:
        pending_keys = pending_keys[: args.limit]
    pending_keys = pending_keys[max(0, args.start - 1):]

    backup = cache_path.with_name(
        f"{cache_path.stem}.before_paddle_{datetime.now():%Y%m%d_%H%M%S}.json"
    )
    shutil.copy2(cache_path, backup)
    print(f"BACKUP {backup}", flush=True)
    print(f"PENDING_TO_PROCESS {len(pending_keys)}", flush=True)

    for index, cache_key in enumerate(pending_keys, start=1):
        old_drafts = groups[cache_key]
        representative = old_drafts[0] if old_drafts else None
        if representative is None or not representative.source_path:
            print(f"PROGRESS {index}/{len(pending_keys)} SKIP sem arquivo", flush=True)
            continue
        image_path = Path(representative.source_path)
        try:
            reading = read_image_text_targeted(image_path)
            new_drafts = parse_document_text(
                reading.text,
                message_id=representative.message_id,
                message_date=representative.message_date,
                source_path=str(image_path),
            )
            if reading.score < 35:
                for draft in new_drafts:
                    if "Leitura da foto com baixa confiança" not in draft.warnings:
                        draft.warnings.append("Leitura da foto com baixa confiança")
                    draft.status = "CONFIRMAR"
            combined_drafts = merge_complementary(old_drafts, new_drafts)
            old_warning_count = sum(len(draft.warnings) for draft in old_drafts)
            new_warning_count = sum(len(draft.warnings) for draft in combined_drafts)
            improved = new_warning_count < old_warning_count
            if improved:
                groups[cache_key] = combined_drafts
            remaining = min(old_warning_count, new_warning_count)
            print(
                f"PROGRESS {index}/{len(pending_keys)} "
                f"{'OK' if improved else 'KEPT_OLD'} "
                f"warnings={remaining} file={image_path.name}",
                flush=True,
            )
        except Exception as exc:
            print(
                f"PROGRESS {index}/{len(pending_keys)} ERROR "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
        write_cache(cache_path, groups)

    all_drafts = [draft for drafts in groups.values() for draft in drafts]
    _apply_message_consensus(all_drafts)
    write_cache(cache_path, groups)
    pending = [draft for draft in all_drafts if draft.warnings]
    warnings = Counter(warning for draft in all_drafts for warning in draft.warnings)
    print("SUMMARY " + json.dumps({
        "cache": str(cache_path),
        "total": len(all_drafts),
        "automatic": len(all_drafts) - len(pending),
        "pending": len(pending),
        "pending_percent": round(len(pending) / len(all_drafts) * 100, 1) if all_drafts else 0,
        "warning_counts": warnings,
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
