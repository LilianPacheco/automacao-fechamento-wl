import json
from collections import Counter,defaultdict
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"runtime_captures"/"revisao_live_2026-07"/"revisao_temporaria.json"
rows=json.loads(p.read_text(encoding="utf-8"))
groups=defaultdict(list)
for r in rows: groups[r.get("message_id")].append(r)
changed=0
for group in groups.values():
    if len(group)<2: continue
    for field in ("work","product","section","unit_volume"):
        vals=[str(r.get(field)) for r in group if r.get(field)]
        if not vals: continue
        counts=Counter(vals); value,n=counts.most_common(1)[0]
        # Consensus only when at least 70% of observed labels agree and there
        # is no close competing value; this avoids copying across mixed albums.
        if n < 2 or n/len(vals) < .70 or (len(counts)>1 and counts.most_common(2)[1][1] >= n*.5): continue
        for r in group:
            if not r.get(field): r[field]=value; changed+=1
    for r in group:
        r["dimensions"]=" ".join(x for x in (r.get("section"),r.get("length")) if x)
        if all(r.get(k) for k in ("work","product","piece","section","length","unit_volume","message_date")):
            r["status"]="PRONTO PARA REVISÃO"
p.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
print("album_consensus",changed)
