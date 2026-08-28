from __future__ import annotations

import html
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from wl_fechamento.label_parser import parse_document_text, LabelDraft
from wl_fechamento.ocr_service import read_image_text
from wl_fechamento.whatsapp_service import WhatsAppProbeResult


def main() -> None:
    capture_root = Path.home() / "AppData" / "Roaming" / "WL Fechamento" / "Capturas"
    sessions = sorted(capture_root.glob("*/sessao_whatsapp.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not sessions:
        raise SystemExit("Nenhuma sessão de captura encontrada.")
    session_path = sessions[0]
    result = WhatsAppProbeResult.from_dict(json.loads(session_path.read_text(encoding="utf-8")))
    # Fast, bounded pass: one OCR orientation per image. A full four-rotation
    # OCR pass can take an hour on a large WhatsApp batch; uncertain rows stay
    # CONFIRMAR for manual review instead of blocking the whole closing.
    def process_attachment(attachment):
        local = []
        if not attachment.mime_type.lower().startswith("image/"):
            return local
        if not attachment.mime_type.lower().startswith("image/"):
            return local
        try:
            reading = read_image_text(Path(attachment.path), rotations=(0, 90, 180, 270))
            date = next((e.message_date for e in result.evidences if e.message_id == attachment.message_id), "")
            parsed = parse_document_text(reading.text, message_id=attachment.message_id, message_date=date, source_path=attachment.path)
            for draft in parsed:
                if reading.score < 35:
                    draft.warnings.append("Leitura da foto com baixa confiança")
                    draft.status = "CONFIRMAR"
            local.extend(parsed)
        except Exception as exc:
            local.append(LabelDraft(message_id=attachment.message_id, source_path=attachment.path, status="CONFIRMAR", warnings=[f"Não foi possível ler a foto: {exc}"]))
        return local

    drafts = []
    images = [a for a in result.captured_attachments if a.mime_type.lower().startswith("image/")]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(process_attachment, attachment) for attachment in images]
        for future in as_completed(futures):
            drafts.extend(future.result())
    drafts.sort(key=lambda d: (d.message_date, d.message_id, d.source_path))
    output_dir = APP_ROOT / "runtime_captures" / "revisao_live_2026-07"
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [asdict(draft) for draft in drafts]
    (output_dir / "revisao_temporaria.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    cards = []
    fields = [("data da mensagem", "message_date"), ("obra", "work"), ("produto", "product"), ("peça", "piece"), ("seção", "section"), ("comprimento", "length"), ("dimensão", "dimensions"), ("volume unitário", "unit_volume"), ("tipo", "type_name"), ("quantidade", "quantity")]
    for index, row in enumerate(rows):
        source = str(row.get("source_path") or "")
        try:
            photo = f'<a href="{html.escape(Path(source).as_uri())}" target="_blank">Abrir foto</a>' if source else "sem foto"
        except ValueError:
            photo = "sem foto"
        inputs = "".join(
            f"<label>{label}<input data-i='{index}' data-k='{key}' value='{html.escape(str(row.get(key, '')))}'></label>"
            for label, key in fields
        )
        warnings = html.escape(" · ".join(row.get("warnings", [])))
        cards.append(
            f"<section><h3>Entrada {index + 1} — {html.escape(str(row.get('message_id', '')))}</h3>"
            f"<p>{photo}</p><p class='warn'>{warnings or 'Sem alerta automático'}</p>"
            f"<div class='grid'>{inputs}<label>status<select data-i='{index}' data-k='status'>"
            f"<option selected>CONFIRMAR</option><option>APROVADO</option><option>REJEITADO</option></select></label></div></section>"
        )
    data = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    page = "<!doctype html><meta charset='utf-8'><title>Revisão temporária WL — sessão atual</title>"
    page += "<style>body{font-family:Arial;background:#f2f5f7;margin:20px}section{background:white;padding:14px;margin:12px 0;border-left:5px solid #d18b00}.warn{color:#9b5c00;font-size:13px}.grid{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:8px}label{font-size:12px;color:#526574}input,select{display:block;width:100%;box-sizing:border-box;padding:7px;margin-top:3px}a{color:#1769aa}button{padding:10px 16px;margin:8px 4px;background:#2879bd;color:white;border:0;border-radius:4px}</style>"
    page += f"<h1>Revisão temporária — sessão atual</h1><p>Fotos capturadas: {len(result.captured_attachments)} · Entradas extraídas: {len(rows)}. Nada será lançado automaticamente.</p>"
    page += "<button onclick='save()'>Salvar revisão</button><button onclick='filterConfirm()'>Mostrar confirmar</button>" + "".join(cards)
    page += "<script>const rows=" + data + ";document.querySelectorAll('input,select').forEach(e=>e.addEventListener('change',()=>rows[+e.dataset.i][e.dataset.k]=e.value));function save(){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(rows,null,2)],{type:'application/json'}));a.download='Revisao_Temporaria_WL.json';a.click()}function filterConfirm(){document.querySelectorAll('section').forEach(s=>s.style.display=s.querySelector('select')?.value==='CONFIRMAR'?'':'none')}</script>"
    output = output_dir / "revisao_temporaria.html"
    output.write_text(page, encoding="utf-8")
    print(json.dumps({"output": str(output), "session": str(session_path), "photos": len(result.captured_attachments), "drafts": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
