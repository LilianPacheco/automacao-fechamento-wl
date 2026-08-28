import json,re
from collections import defaultdict
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"runtime_captures"/"revisao_live_2026-07"/"revisao_temporaria.json"
rows=json.loads(p.read_text(encoding="utf-8"))
def norm(v):
    s=str(v or "").upper().replace(" ","").replace(".",",")
    if re.fullmatch(r"\d+,\d+",s):
        s=s.rstrip("0").rstrip(",")
    return s
groups=defaultdict(list)
for r in rows: groups[r.get("message_id")].append(r)
changed=0
for group in groups.values():
    if len(group)<2: continue
    for field in ("piece","section","length","unit_volume","work","product"):
        others=[k for k in ("piece","section","length","unit_volume","work","product") if k!=field]
        for row in group:
            if row.get(field): continue
            candidates=[]
            for x in group:
                if not x.get(field): continue
                if all(norm(row.get(k))==norm(x.get(k)) for k in others): candidates.append(x[field])
            if len(set(candidates))==1:
                row[field]=candidates[0]; changed+=1
    for row in group:
        row["dimensions"]=" ".join(x for x in (row.get("section"),row.get("length")) if x)
p.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
print("normalized_album_propagation",changed)
