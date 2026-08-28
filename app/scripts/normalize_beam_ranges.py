"""Classify every VIGA by the length bands used in the workbook."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "runtime_captures" / "revisao_live_2026-07"
path = root / "revisao_temporaria.json"
rows = json.loads(path.read_text(encoding="utf-8"))


def beam_type(length):
    try:
        value = float(str(length).replace(".", "").replace(",", "."))
    except (TypeError, ValueError):
        return ""
    if value <= 6:
        return "VIGA ATÉ 6m"
    if value <= 8.9:
        return "VIGA 6,1 ATÉ 8,9m"
    if value <= 10:
        return "VIGA 9m ATÉ 10m"
    if value <= 15.55:
        return "VIGA 10,1m ATÉ 15,55m"
    return "VIGA 15,56m ATÉ 25m"


changed = 0
synced = 0
for row in rows:
    if "VIGA" in str(row.get("product") or "").upper():
        target = beam_type(row.get("length"))
        if target:
            if row.get("type_name") != target:
                row["type_name"] = target
                changed += 1
            if row.get("product") != target:
                row["product"] = target
                synced += 1
    elif row.get("type_name"):
        # Produto e tipo usam a mesma lista fechada da tabela.
        if row.get("product") != row["type_name"]:
            row["product"] = row["type_name"]
            synced += 1

path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"vigas_classificadas={changed} produtos_sincronizados={synced}")
