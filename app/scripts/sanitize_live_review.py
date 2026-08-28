import json, re
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "runtime_captures" / "revisao_live_2026-07"
path = root / "revisao_temporaria.json"
rows = json.loads(path.read_text(encoding="utf-8"))
section_re = re.compile(r"^(?:E=\d{1,3}(?:[.,]\d+)?|\d{1,3}(?:[.,]\d+)?X\d{1,3}(?:[.,]\d+)?(?:/\d{1,3}(?:[.,]\d+)?)?)$")
for row in rows:
    warnings = list(row.get("warnings") or [])
    section = str(row.get("section") or "").replace(" ", "")
    if section and not section_re.fullmatch(section):
        row["section"] = ""
        row["dimensions"] = str(row.get("length") or "")
        if "Confirmar seção" not in warnings:
            warnings.append("Confirmar seção: formato inválido")
    try:
        volume = float(str(row.get("unit_volume") or "").replace(",", "."))
    except ValueError:
        volume = None
    if volume is not None and volume > 10:
        row["unit_volume"] = None
        warnings.append("Confirmar volume unitário: valor parece peso/QR, não volume")
    if warnings:
        row["status"] = "CONFIRMAR"
    row["warnings"] = list(dict.fromkeys(warnings))
path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"sanitized={len(rows)}")
