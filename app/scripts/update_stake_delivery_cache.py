from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from wl_fechamento.label_parser import parse_document_text


CAPTURES = Path.home() / "AppData" / "Roaming" / "WL Fechamento" / "Capturas"


def main() -> None:
    source = max(
        CAPTURES.glob("*/revisao_temporaria.json"),
        key=lambda path: path.stat().st_mtime,
    )
    loaded = json.loads(source.read_text(encoding="utf-8"))
    changed = 0

    collections = loaded.values() if isinstance(loaded, dict) else (loaded,)
    for rows in collections:
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            raw = str(row.get("ocr_text") or "")
            upper = raw.upper()
            if not all(marker in upper for marker in ("ESTACA", "DIMENSAO", "QUANTIDADE", "METROS")):
                continue
            parsed = parse_document_text(
                raw,
                message_id=str(row.get("message_id") or ""),
                message_date=str(row.get("message_date") or ""),
                source_path=str(row.get("source_path") or ""),
            )
            if not parsed or parsed[0].product != "ESTACA":
                continue
            rows[index] = asdict(parsed[0])
            changed += 1

    if changed:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = source.with_name(f"revisao_temporaria.antes_estaca_{stamp}.json")
        shutil.copy2(source, backup)
        temporary = source.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(loaded, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(source)
        print(f"updated={changed}")
        print(f"backup={backup}")
    else:
        print("updated=0")


if __name__ == "__main__":
    main()
