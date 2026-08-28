from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from wl_fechamento.label_parser import parse_document_text  # noqa: E402
from wl_fechamento.ocr_service import read_image_text  # noqa: E402


def latest_review_cache() -> Path:
    root = Path(os.environ["APPDATA"]) / "WL Fechamento" / "Capturas"
    candidates = sorted(
        root.glob("*/revisao_temporaria.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise SystemExit("Nenhum cache de revisão foi encontrado.")
    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--path", type=Path)
    args = parser.parse_args()

    cache_path = latest_review_cache()
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    entries = [
        item
        for group in cached.values()
        for item in (group if isinstance(group, list) else [group])
        if isinstance(item, dict)
    ]
    pending = [item for item in entries if item.get("warnings")]
    start = max(0, args.start - 1)
    if args.path:
        sample = [{
            "source_path": str(args.path),
            "message_date": "02/08/2026",
            "warnings": ["teste"],
        }]
    else:
        sample = pending[start : start + max(1, args.limit)]
    old_warning_total = 0
    new_warning_total = 0
    completed = 0
    rows: list[dict[str, object]] = []

    for index, item in enumerate(sample, start=1):
        image_path = Path(item["source_path"])
        old_warnings = list(item.get("warnings", []))
        old_warning_total += len(old_warnings)
        reading = read_image_text(image_path)
        parsed_rows = parse_document_text(
            reading.text,
            message_date=item.get("message_date", ""),
            source_path=str(image_path),
        )
        parsed = parsed_rows[0]
        new_warnings = list(parsed.warnings)
        new_warning_total += len(new_warnings)
        if not new_warnings:
            completed += 1
        row = {
            "index": index,
            "file": image_path.name,
            "old_warnings": old_warnings,
            "new_warnings": new_warnings,
            "piece": parsed.piece,
            "section": parsed.section,
            "length": parsed.length,
            "unit_volume": parsed.unit_volume,
            "work": parsed.work,
            "product": parsed.product,
            "ocr_text": reading.text,
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)

    reduction = (
        round((old_warning_total - new_warning_total) / old_warning_total * 100, 1)
        if old_warning_total
        else 0.0
    )
    summary = {
        "cache": str(cache_path),
        "sample": len(sample),
        "old_warning_total": old_warning_total,
        "new_warning_total": new_warning_total,
        "warning_reduction_percent": reduction,
        "fully_completed": completed,
    }
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
