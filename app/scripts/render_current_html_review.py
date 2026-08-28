from __future__ import annotations

import html
import json
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CAPTURES = Path.home() / "AppData" / "Roaming" / "WL Fechamento" / "Capturas"
source = max(CAPTURES.glob("*/revisao_temporaria.json"), key=lambda p: p.stat().st_mtime)
loaded = json.loads(source.read_text(encoding="utf-8"))
rows = [item for values in loaded.values() for item in values if isinstance(item, dict)] if isinstance(loaded, dict) else loaded
prelog_dir = Path(r"C:\Users\lilia\Downloads\FECHAMENTOS PRELOG")
out_dir = prelog_dir / "Revisão Fechamento WL"
if not prelog_dir.exists():
    out_dir = APP_ROOT / "runtime_captures" / "revisao_live_2026-08"
try:
    out_dir.mkdir(parents=True, exist_ok=True)
    probe = out_dir / ".wl_write_probe"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)
except PermissionError:
    # FECHAMENTOS PRELOG may be protected by Windows/OneDrive. Keep the
    # review in the application's writable capture folder instead of falling
    # back to the legacy table window.
    out_dir = APP_ROOT / "runtime_captures" / "revisao_live_2026-08"
    out_dir.mkdir(parents=True, exist_ok=True)

options = ["BLOCO", "ESTACA", "ESCADA", "MURO", "PAINEL", "PILAR", "VIGA", "LAJE", "VIGA 15,56m ATÉ 25m", "VIGA 10,1m ATÉ 15,55m", "VIGA 9m ATÉ 10m", "VIGA 6,1 ATÉ 8,9m", "VIGA ATÉ 6m", "LAJE ALVEOLAR", "METRO CÚBICO", "VIGA TERÇA"]
fields = [("data da mensagem", "message_date"), ("obra", "work"), ("produto", "product"), ("peça", "piece"), ("seção", "section"), ("comprimento", "length"), ("dimensão", "dimensions"), ("volume unitário", "unit_volume"), ("tipo", "type_name"), ("quantidade", "quantity")]

def status(row: dict) -> str:
    value = str(row.get("status", "")).upper()
    if value in {"APROVADO", "REJEITADO", "CONFIRMADO"}:
        return value
    # CONFIRMAR/PENDENTE are explicit review decisions. Filling one or even all
    # fields must not silently promote the entry; only the situation selector
    # can do that.
    if value in {"CONFIRMAR", "PENDENTE"}:
        return "PENDENTE"
    if str(row.get("product") or row.get("type_name") or "").upper() == "ESTACA":
        required = ("message_date", "work", "product", "piece", "section", "quantity", "type_name")
    else:
        required = ("message_date", "work", "product", "piece", "section", "length", "unit_volume")
    return "CONFIRMADO" if all(str(row.get(key) or "").strip() for key in required) else "PENDENTE"

parts = ["<!doctype html><meta charset='utf-8'><title>Revisão temporária do fechamento WL</title>", """<style>body{font-family:Arial;background:#f2f5f7;margin:20px;color:#263746}header{position:sticky;top:0;z-index:5;background:#f2f5f7;padding:8px 0 14px;border-bottom:1px solid #ccd6dc}h1{margin:4px 0 8px}.filters{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.filter{border:1px solid #3178a8;border-radius:5px;background:#fff;padding:8px 13px;cursor:pointer}.filter.active{background:#1769aa;color:#fff}.count{font-weight:bold;margin-left:8px}section{background:#fff;padding:14px;margin:12px 0;border-left:5px solid #d18b00}section.ok{border-left-color:#3b9148}section.no{border-left-color:#b33a3a}.grid{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:8px}label{font-size:12px;color:#526574}input,select{display:block;width:100%;box-sizing:border-box;padding:7px;margin-top:3px}.warn{color:#9b5c00;font-size:13px}a{color:#1769aa}.hidden{display:none!important}@media(max-width:800px){.grid{grid-template-columns:repeat(2,minmax(140px,1fr))}}</style>""", f"<header><h1>Revisão temporária do fechamento WL</h1><p>Fotos analisadas: {len(rows)} · Campos incertos ficam pendentes.</p><div class='filters'><span>Exibir:</span><button class='filter active' data-filter='TODOS'>Todos</button><button class='filter' data-filter='PENDENTE'>Pendente</button><button class='filter' data-filter='CONFIRMADO'>Confirmado</button><button class='filter' data-filter='APROVADO'>Aprovado</button><button class='filter' data-filter='REJEITADO'>Rejeitado</button><span class='count' id='count'></span></div></header>"]
for i, row in enumerate(rows):
    current = status(row)
    link = f"<a href='{html.escape(Path(str(row.get('source_path'))).as_uri())}' target='_blank'>Abrir foto original</a>" if row.get("source_path") else "sem foto"
    controls = []
    for label, key in fields:
        value = html.escape(str(row.get(key) or ""))
        if key in {"product", "type_name"}:
            opts = "<option value=''>Selecione...</option>" + "".join(f"<option{' selected' if x == row.get(key) else ''}>{html.escape(x)}</option>" for x in options)
            controls.append(f"<label>{label}<select data-k='{key}'>{opts}</select></label>")
        else:
            controls.append(f"<label>{label}<input data-k='{key}' value='{value}'></label>")
    states = "".join(f"<option{' selected' if x == current else ''}>{x}</option>" for x in ("PENDENTE", "CONFIRMADO", "APROVADO", "REJEITADO"))
    warning = html.escape(" · ".join(row.get("warnings") or []) or "Sem alerta automático")
    parts.append(f"<section data-status='{current}'><h3>Entrada {i+1}</h3><p>{link}</p><p class='warn'>{warning}</p><div class='grid'>{''.join(controls)}<label>situação<select data-status>{states}</select></label></div></section>")
parts.append("""<script>const cards=[...document.querySelectorAll('section[data-status]')],buttons=[...document.querySelectorAll('[data-filter]')],count=document.getElementById('count');function apply(f){cards.forEach(c=>c.classList.toggle('hidden',f!=='TODOS'&&c.dataset.status!==f));buttons.forEach(b=>b.classList.toggle('active',b.dataset.filter===f));count.textContent=`${cards.filter(c=>!c.classList.contains('hidden')).length} entrada(s)`}buttons.forEach(b=>b.onclick=()=>apply(b.dataset.filter));document.querySelectorAll('select[data-status]').forEach(s=>s.onchange=()=>{s.closest('section').dataset.status=s.value;apply(document.querySelector('.filter.active').dataset.filter)});apply('TODOS');</script>""")
(out_dir / "revisao_temporaria.html").write_text("\n".join(parts), encoding="utf-8")
print(out_dir / "revisao_temporaria.html")
