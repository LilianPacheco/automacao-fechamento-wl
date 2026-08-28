from __future__ import annotations

import html
import json
import argparse
from dataclasses import asdict
from pathlib import Path
import sys

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from wl_fechamento.chrome_bridge import load_saved_whatsapp_session
from wl_fechamento.label_parser import parse_document_text
from wl_fechamento.review_service import build_review_drafts


DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "runtime_captures" / "sessao_definitiva_v141"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    root = args.directory.resolve()
    output = root / "revisao_temporaria.html"
    result = load_saved_whatsapp_session(root)
    cached_drafts = build_review_drafts(result, retry_ocr_errors=False)
    grouped: dict[tuple[str, str], list] = {}
    for draft in cached_drafts:
        grouped.setdefault((draft.message_id, draft.source_path), []).append(draft)
    drafts = []
    for (message_id, source_path), items in grouped.items():
        ocr_text = next((item.ocr_text for item in items if item.ocr_text), "")
        if ocr_text:
            reparsed = parse_document_text(
                ocr_text,
                message_id=message_id,
                message_date=items[0].message_date,
                source_path=source_path,
            )
            drafts.extend(reparsed or items)
        else:
            drafts.extend(items)
    rows = []
    for draft in drafts:
        item = asdict(draft)
        if item.get("status") not in {"APROVADO", "REJEITADO"}:
            item["status"] = "CONFIRMAR"
        item["source_file"] = Path(draft.source_path).name
        rows.append(item)
    data = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    photo_count = len(result.captured_attachments)
    entry_count = len(rows)
    storage_key = "wl-review-" + root.name
    page = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Revisão temporária — Fechamento WL</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f3f6f8;color:#172b3a}}
header{{background:#173e69;color:white;padding:20px 28px;position:sticky;top:0;z-index:3}}
h1{{font-size:24px;margin:0 0 7px}} .sub{{opacity:.9}}
.tools{{padding:14px 24px;background:white;position:sticky;top:88px;z-index:2;border-bottom:1px solid #ccd5dc}}
button{{padding:9px 14px;margin-right:8px;border:0;border-radius:4px;background:#2879bd;color:white;font-weight:600;cursor:pointer}}
button.secondary{{background:#637484}} #summary{{margin-left:12px;font-weight:600}}
main{{padding:18px 24px}} .card{{background:white;border:1px solid #ccd5dc;border-radius:7px;margin-bottom:14px;padding:14px}}
.card.confirm{{border-left:6px solid #d38b00}} .card.ready{{border-left:6px solid #2f8b57}}
.top{{display:flex;justify-content:space-between;gap:12px;margin-bottom:10px}} .warning{{color:#9b5c00;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:10px}}
label{{font-size:12px;color:#526574}} input,select{{display:block;width:100%;box-sizing:border-box;padding:7px;margin-top:3px;border:1px solid #aebbc5;border-radius:3px}}
.photo{{color:#1769aa;text-decoration:none;font-weight:600}} .hidden{{display:none}} .note{{padding:12px 24px;background:#fff4d6}}
@media(max-width:900px){{.grid{{grid-template-columns:repeat(2,minmax(140px,1fr))}}}}
</style></head><body>
<header><h1>Revisão temporária — Fechamento WL</h1><div class="sub">{photo_count} fotos • {entry_count} entradas • nada lançado na planilha</div></header>
<div class="note">Confira principalmente os cartões amarelos. A automação não adivinhou códigos ou medidas duvidosas.</div>
<div class="tools"><button onclick="filterRows('all')">Mostrar todas</button><button class="secondary" onclick="filterRows('confirm')">Somente confirmar</button><button onclick="exportReview()">Salvar revisão</button><span id="summary"></span></div>
<main id="cards"></main>
<script>
const original={data};
let rows=JSON.parse(localStorage.getItem('{storage_key}')||'null')||original;
const fields=[['message_date','Data da mensagem'],['work','Obra'],['product','Produto'],['piece','Peça'],['section','Seção'],['length','Comprimento'],['dimensions','Dimensão'],['unit_volume','Volume unitário'],['type_name','Tipo'],['quantity','Quantidade']];
function esc(v){{return String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));}}
function render(){{const host=document.getElementById('cards');host.innerHTML=rows.map((r,i)=>`<section class="card ${{r.status==='CONFIRMAR'?'confirm':'ready'}}" data-state="${{r.status==='CONFIRMAR'?'confirm':'ready'}}"><div class="top"><div><b>Entrada ${{i+1}}</b> • <a class="photo" target="_blank" href="${{encodeURI(r.source_file)}}">abrir foto</a></div><div class="warning">${{esc((r.warnings||[]).join(' • '))}}</div></div><div class="grid">${{fields.map(([k,l])=>`<label>${{l}}<input data-i="${{i}}" data-k="${{k}}" value="${{esc(r[k])}}"></label>`).join('')}}<label>Decisão<select data-i="${{i}}" data-k="status"><option ${{r.status==='CONFIRMAR'?'selected':''}}>CONFIRMAR</option><option ${{r.status==='APROVADO'?'selected':''}}>APROVADO</option><option ${{r.status==='REJEITADO'?'selected':''}}>REJEITADO</option></select></label></div></section>`).join('');host.querySelectorAll('input,select').forEach(e=>e.addEventListener('change',()=>{{rows[+e.dataset.i][e.dataset.k]=e.value;localStorage.setItem('{storage_key}',JSON.stringify(rows));renderSummary();}}));renderSummary();}}
function renderSummary(){{const c=rows.reduce((a,r)=>(a[r.status]=(a[r.status]||0)+1,a),{{}});document.getElementById('summary').textContent=`Aprovadas: ${{c.APROVADO||0}} • Confirmar: ${{c.CONFIRMAR||0}} • Rejeitadas: ${{c.REJEITADO||0}}`;}}
function filterRows(kind){{document.querySelectorAll('.card').forEach(c=>c.classList.toggle('hidden',kind!=='all'&&c.dataset.state!==kind));}}
function exportReview(){{const blob=new Blob([JSON.stringify(rows,null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='Revisao_Temporaria_WL.json';a.click();URL.revokeObjectURL(a.href);}}
render();
</script></body></html>"""
    output.write_text(page, encoding="utf-8")
    print(json.dumps({"output": str(output), "photos": photo_count, "entries": entry_count}, ensure_ascii=False))


if __name__ == "__main__":
    main()
