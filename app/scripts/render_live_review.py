import html
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "runtime_captures" / "revisao_live_2026-07"
rows = json.loads((root / "revisao_temporaria.json").read_text(encoding="utf-8"))

labels = [
    ("data da mensagem", "message_date"),
    ("obra", "work"),
    ("produto", "product"),
    ("peça", "piece"),
    ("seção", "section"),
    ("comprimento", "length"),
    ("dimensão", "dimensions"),
    ("volume unitário", "unit_volume"),
    ("tipo", "type_name"),
    ("quantidade", "quantity"),
]

PRODUCT_OPTIONS = [
    "BLOCO", "ESTACA", "ESCADA", "MURO", "PAINEL", "PILAR", "VIGA", "LAJE",
    "VIGA 15,56m ATÉ 25m", "VIGA 10,1m ATÉ 15,55m", "VIGA 9m ATÉ 10m",
    "VIGA 6,1 ATÉ 8,9m", "VIGA ATÉ 6m", "LAJE ALVEOLAR", "METRO CÚBICO", "VIGA TERÇA",
]
TYPE_OPTIONS = [
    "BLOCO", "ESTACA", "ESCADA", "MURO", "PAINEL", "PILAR",
    "VIGA 15,56m ATÉ 25m", "VIGA 10,1m ATÉ 15,55m", "VIGA 9m ATÉ 10m",
    "VIGA 6,1 ATÉ 8,9m", "VIGA ATÉ 6m", "LAJE ALVEOLAR", "METRO CÚBICO", "VIGA TERÇA",
]


def situation(value, row):
    value = str(value or "").strip().upper()
    if value == "APROVADO":
        return "APROVADO"
    if value == "REJEITADO":
        return "REJEITADO"
    if value == "CONFIRMADO":
        return "CONFIRMADO"
    if str(row.get("product") or row.get("type_name") or "").upper() == "ESTACA":
        required = ("message_date", "work", "product", "piece", "section", "quantity", "type_name")
    else:
        required = ("message_date", "work", "product", "piece", "section", "length", "unit_volume")
    # A entrada só fica automaticamente confirmada quando todos os dados
    # necessários foram lidos; qualquer lacuna continua pendente.
    if all(str(row.get(key) or "").strip() for key in required):
        return "CONFIRMADO"
    return "PENDENTE"


def select_field(label, key, current, options, index):
    current = str(current or "").strip()
    option_html = "<option value=''>Selecione...</option>" + "".join(
        f"<option{' selected' if option == current else ''}>{html.escape(option)}</option>"
        for option in options
    )
    return f"<label>{label}<select data-i='{index}' data-k='{key}'>{option_html}</select></label>"


parts = [
    "<!doctype html><meta charset='utf-8'><title>Revisão temporária WL</title>",
    """<style>
body{font-family:Arial;background:#f2f5f7;margin:20px;color:#263746}
header{position:sticky;top:0;z-index:5;background:#f2f5f7;padding:8px 0 14px;border-bottom:1px solid #ccd6dc}
h1{margin:4px 0 8px}.summary{margin:5px 0 12px}.filters{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.filter{border:1px solid #3178a8;border-radius:5px;background:#fff;padding:8px 13px;cursor:pointer}
.filter.active{background:#1769aa;color:white}.count{font-weight:bold;margin-left:8px}
section{background:#fff;padding:14px;margin:12px 0;border-left:5px solid #d18b00}
section[data-status='APROVADO'],section[data-status='CONFIRMADO']{border-left-color:#3b9148}
section[data-status='REJEITADO']{border-left-color:#b33a3a}.grid{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:8px}
label{font-size:12px;color:#526574}input,select{display:block;width:100%;box-sizing:border-box;padding:7px;margin-top:3px}
.warn{color:#9b5c00;font-size:13px}a{color:#1769aa}.hidden{display:none!important}
@media(max-width:800px){.grid{grid-template-columns:repeat(2,minmax(140px,1fr))}}
</style>""",
    f"<header><h1>Revisão temporária do fechamento WL</h1><p class='summary'>Fotos analisadas: 192 · Entradas: {len(rows)}. Campos incertos ficam pendentes.</p><div class='filters'><span>Exibir:</span><button class='filter active' data-filter='TODOS'>Todos</button><button class='filter' data-filter='PENDENTE'>Pendente</button><button class='filter' data-filter='CONFIRMADO'>Confirmado</button><button class='filter' data-filter='APROVADO'>Aprovado</button><button class='filter' data-filter='REJEITADO'>Rejeitado</button><span class='count' id='count'></span></div></header>",
]

for i, row in enumerate(rows):
    src = str(row.get("source_path") or "")
    link = f"<a href='{html.escape(Path(src).as_uri())}' target='_blank'>Abrir foto original</a>" if src else "sem foto"
    fields = "".join(
        select_field(lab, key, row.get(key), PRODUCT_OPTIONS if key == "product" else TYPE_OPTIONS, i)
        if key in ("product", "type_name") else
        f"<label>{lab}<input data-i='{i}' data-k='{key}' value='{html.escape(str(row.get(key) or ''))}'></label>"
        for lab, key in labels
    )
    warns = " · ".join(row.get("warnings") or []) or "Sem alerta automático"
    current = situation(row.get("status"), row)
    options = "".join(
        f"<option{' selected' if option == current else ''}>{option.title()}</option>"
        for option in ("PENDENTE", "CONFIRMADO", "APROVADO", "REJEITADO")
    )
    parts.append(
        f"<section data-status='{current}'><h3>Entrada {i+1}</h3><p>{link}</p>"
        f"<p class='warn'>{html.escape(warns)}</p><div class='grid'>{fields}"
        f"<label>situação<select data-status-select>{options}</select></label></div></section>"
    )

parts.append(
    """<script>
const cards=[...document.querySelectorAll('section[data-status]')];
const buttons=[...document.querySelectorAll('[data-filter]')];
const count=document.getElementById('count');
function apply(filter){
  cards.forEach(c=>c.classList.toggle('hidden',filter!=='TODOS'&&c.dataset.status!==filter));
  buttons.forEach(b=>b.classList.toggle('active',b.dataset.filter===filter));
  count.textContent=`${cards.filter(c=>!c.classList.contains('hidden')).length} entrada(s)`;
}
buttons.forEach(b=>b.addEventListener('click',()=>apply(b.dataset.filter)));
document.querySelectorAll('[data-status-select]').forEach(s=>s.addEventListener('change',()=>{
  const value=s.value.toUpperCase(); const card=s.closest('section'); card.dataset.status=value;
  card.style.borderLeftColor=value==='PENDENTE'?'#d18b00':(value==='REJEITADO'?'#b33a3a':'#3b9148'); apply(document.querySelector('.filter.active').dataset.filter);
}));
document.querySelectorAll('input').forEach(e=>e.addEventListener('change',()=>{e.style.background='#fff3cd'}));
apply('TODOS');
</script>"""
)

(root / "revisao_temporaria.html").write_text("\n".join(parts), encoding="utf-8")
print(f"rendered={len(rows)}")
