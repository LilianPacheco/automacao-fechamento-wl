import html, json
import sys
from dataclasses import asdict
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "runtime_captures" / "quinzena_consolidada_2026-07_v180"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wl_fechamento.label_parser import parse_document_text
session = json.loads((root / "sessao_whatsapp.json").read_text(encoding="utf-8"))
rows = []
cache_path = root / "revisao_temporaria.json"
if cache_path.exists():
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    for values in cache.values():
        if isinstance(values, list):
            for value in values:
                if not isinstance(value, dict):
                    continue
                text = value.get("ocr_text", "")
                reparsed = parse_document_text(
                    text,
                    message_id=value.get("message_id", ""),
                    message_date=value.get("message_date", ""),
                    source_path=value.get("source_path", ""),
                ) if text else []
                rows.extend([asdict(item) for item in reparsed] or [value])
if not rows:
    rows = list(session.get("evidences", []))
links = {}
for att in session.get("captured_attachments", []):
    links.setdefault(att.get("message_id"), []).append(att.get("filename", ""))
cards = []
for i, row in enumerate(rows):
    mid = str(row.get("message_id", ""))
    files = links.get(mid, [])
    photo = " ".join(f'<a href="{html.escape(f)}" target="_blank">foto {n}</a>' for n, f in enumerate(files, 1)) or "sem foto copiada"
    fields = ["message_date", "work", "product", "piece", "section", "length", "dimensions", "unit_volume", "type_name", "quantity"]
    vals = "".join(f"<label>{k}<input data-i='{i}' data-k='{k}' value='{html.escape(str(row.get(k, '')))}'></label>" for k in fields)
    warnings = html.escape(' · '.join(row.get('warnings', [])))
    cards.append(f"<section><h3>Entrada {i + 1} — {html.escape(mid)}</h3><p>{photo}</p><p class='warn'>{warnings or 'Sem alerta automático'}</p><div class='grid'>{vals}<label>status<select data-i='{i}' data-k='status'><option selected>CONFIRMAR</option><option>APROVADO</option><option>REJEITADO</option></select></label></div></section>")
data = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
page = ("<!doctype html><meta charset='utf-8'><title>Revisão temporária WL</title><style>body{font-family:Arial;background:#f2f5f7;margin:20px}section{background:white;padding:14px;margin:12px 0;border-left:5px solid #d18b00}.warn{color:#9b5c00;font-size:13px}.grid{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:8px}label{font-size:12px;color:#526574}input,select{display:block;width:100%;box-sizing:border-box;padding:7px;margin-top:3px}a{color:#1769aa;margin-right:10px}button{padding:10px 16px;margin:8px 4px;background:#2879bd;color:white;border:0;border-radius:4px}</style><h1>Revisão temporária — Fechamento WL</h1><p>Revise e corrija os campos. Nada será lançado na planilha automaticamente.</p><button onclick='save()'>Salvar revisão</button><button onclick='filterConfirm()'>Mostrar confirmar</button>" + ''.join(cards) + "<script>const rows=" + data + ";document.querySelectorAll('input,select').forEach(e=>e.addEventListener('change',()=>rows[+e.dataset.i][e.dataset.k]=e.value));function save(){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(rows,null,2)],{type:'application/json'}));a.download='Revisao_Temporaria_WL.json';a.click()}function filterConfirm(){document.querySelectorAll('section').forEach(s=>s.style.display=s.querySelector('select')?.value==='CONFIRMAR'?'':'none')}</script>")
(root / "revisao_temporaria.html").write_text(page, encoding="utf-8")
print(json.dumps({"output": str(root / "revisao_temporaria.html"), "messages": len(rows), "photos": len(session.get("captured_attachments", []))}, ensure_ascii=False))
