import json
from collections import defaultdict
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"runtime_captures"/"revisao_live_2026-07"/"revisao_temporaria.json"
rows=json.loads(p.read_text(encoding="utf-8"))
changed=0
for row in rows:
    siblings=[x for x in rows if x.get("message_id")==row.get("message_id") and x is not row]
    # A same-album sibling is usable only when every other label field agrees
    # and exactly one sibling supplies the missing value.
    for field in ("piece","section","length","unit_volume","work","product"):
        if row.get(field): continue
        candidates=[]
        for x in siblings:
            if not x.get(field): continue
            keys=("work","product","piece","section","length","unit_volume")
            if all(k==field or row.get(k)==x.get(k) for k in keys): candidates.append(x[field])
        if len(set(candidates))==1:
            row[field]=candidates[0]; changed+=1
    row["dimensions"]=" ".join(x for x in (row.get("section"),row.get("length")) if x)
    if all(row.get(k) for k in ("work","product","piece","section","length","unit_volume","message_date")):
        row["status"]="PRONTO PARA REVISÃO"
p.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
print("propagated",changed)
