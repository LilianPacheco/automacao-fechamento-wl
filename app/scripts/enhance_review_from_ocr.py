import json, re, unicodedata
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "runtime_captures" / "revisao_live_2026-07"
path = root / "revisao_temporaria.json"
rows = json.loads(path.read_text(encoding="utf-8"))

def plain(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).upper()

def dec(s):
    return s.replace(".", ",") if "," not in s else s

def addwarn(row, msg):
    row["warnings"] = list(dict.fromkeys((row.get("warnings") or []) + [msg]))

for row in rows:
    text = plain(row.get("ocr_text"))
    # Windows OCR commonly renders the digit 1 as capital I inside codes.
    text = re.sub(r"\b(P[HLM]|V[PRT]|P[A-Z])\s*-?\s*I\b", r"\g<1>-1", text)
    if not text:
        continue
    # Known works; only accept a work when a recognizable marker is present.
    if "VENTISOL" in text and "CUBATA" in text:
        row["work"] = "VENTISOL - GUARDA DO CUBATAO"
    elif "VENTISOL" in text and ("VERTICAL" in text or "ERTICAL" in text):
        row["work"] = "VENTISOL - GALPAO VERTICAL 282"
    elif ("AMPLIACAO" in text or "AMPL4CAO" in text) and "ALUMIN" in text:
        row["work"] = "AMPLIACAO ALUMINIO SJ"
    elif "MKM" in text and "GALPAO" in text:
        row["work"] = "MKM GALPAO COMERCIAL"
    elif "CEJEN" in text and "IMBITUBA" in text:
        row["work"] = "CEJEN - PORTO IMBITUBA"

    # Product is a normalized category, never the dimension or qualifier.
    for marker, product in (("PAINEL", "PAINEL"), ("PILAR", "PILAR"), ("VIGA", "VIGA"), ("BLOCO", "BLOCO"), ("MURO", "MURO"), ("ESCADA", "ESCADA")):
        if marker in text:
            row["product"] = product
            if product == "PILAR": row["type_name"] = "PILAR"
            break

    # Section/dimension, including OCR forms E=IO and E—12.
    e = re.search(r"\bE\s*(?:=|-|—|:)?\s*(IO|\d{1,3})\b", text)
    dims = re.findall(r"\b\d{1,3}\s*[X*]\s*\d{1,3}\b", text)
    if e:
        val = "10" if e.group(1) == "IO" else e.group(1)
        row["section"] = "E=" + val
    elif dims:
        token = re.sub(r"\s+", "", dims[-1]).replace("*", "X")
        row["section"] = token

    # Piece code; prefer code immediately before/after Peca, otherwise a
    # unique code-shaped token. QR numbers are numeric and therefore ignored.
    piece_patterns = re.findall(r"\b(?:PH|PL|PM|PP|PA|VP|VL|VPR|VPT|VR|B)\s*-?\s*[\dIO]{1,3}(?:-[A-Z])?\b", text)
    if piece_patterns:
        candidate = re.sub(r"\s+", "", piece_patterns[-1]).replace("- ", "-")
        candidate = re.sub(r"(?<=-)I$", "1", candidate)
        row["piece"] = candidate

    # Length is the first plausible 1–2 digit measure after Comprimento.
    m = re.search(r"COMPR\w{0,8}[^0-9]{0,20}(\d{1,3}[,.]\d{2,3})", text)
    if m and float(m.group(1).replace(",", ".")) <= 35:
        row["length"] = dec(m.group(1))
    else:
        candidates = [x for x in re.findall(r"\b\d{1,3}[,.]\d{3}\b", text) if float(x.replace(",", ".")) <= 35]
        if candidates:
            row["length"] = dec(candidates[0])

    # Unit volume must be next to Vol/Voi (or immediately before it), and must
    # be a plausible cubic-metre value. Never use a weight or QR number.
    near = re.findall(r"(?:VOL|VOI|V0L).*?(\d{1,2}[,.]\d{3})(?=\s*(?:\(M3\)|M3|$))", text)
    near += re.findall(r"(\d{1,2}[,.]\d{3})\s*(?:VOL|VOI|V0L)", text)
    if near:
        value = dec(near[-1])
        try:
            if float(value.replace(",", ".")) <= 10:
                row["unit_volume"] = value
        except ValueError:
            pass

    row["dimensions"] = " ".join(x for x in (row.get("section"), row.get("length")) if x)
    required = (row.get("work"), row.get("product"), row.get("piece"), row.get("section"), row.get("length"), row.get("unit_volume"), row.get("message_date"))
    if all(required):
        row["status"] = "PRONTO PARA REVISÃO"
        row["warnings"] = [w for w in (row.get("warnings") or []) if not w.lower().startswith("confirmar")]
    else:
        row["status"] = "CONFIRMAR"

path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
print("enhanced", len(rows))
