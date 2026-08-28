import json,re
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"runtime_captures"/"revisao_live_2026-07"/"revisao_temporaria.json"
rows=json.loads(p.read_text(encoding="utf-8"))
for row in rows:
    product=str(row.get("product") or "").upper()
    if "PILAR" in product: row["product"]="PILAR"; row["type_name"]="PILAR"
    elif "PAINEL" in product: row["product"]="PAINEL"
    elif "VIGA" in product: row["product"]="VIGA"
    elif "LAJE" in product: row["product"]="LAJE"
    elif "BLOCO" in product: row["product"]="BLOCO"
    elif "MURO" in product: row["product"]="MURO"
    m=re.search(r"\b(\d{1,3}X\d{1,3})\b", product)
    if m:
        if not row.get("section"): row["section"]=m.group(1)
        row["product"]=re.sub(r"\s*\d{1,3}X\d{1,3}\s*", " ", row["product"]).strip() or row["product"]
        row["dimensions"]=" ".join(x for x in (row.get("section"),row.get("length")) if x)
        row["status"]="CONFIRMAR"
p.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
print("normalizados",len(rows))
