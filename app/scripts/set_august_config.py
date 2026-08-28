from __future__ import annotations

import json
import os
from pathlib import Path


workspace = Path(__file__).resolve().parents[2]
config_dir = Path(os.environ.get("APPDATA", Path.home())) / "WL Fechamento"
config_dir.mkdir(parents=True, exist_ok=True)
config_path = config_dir / "config.json"
workbook = workspace / "MEDIÇÕES AWL - 2026 - PRONTO AGOSTO.xlsx"
config_path.write_text(
    json.dumps(
        {
            "workbook_path": str(workbook),
            "last_year": 2026,
            "last_month": 8,
            "last_fortnight": 1,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print(config_path)
print(workbook)
