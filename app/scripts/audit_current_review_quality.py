from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from wl_fechamento.label_parser import (  # noqa: E402
    LabelDraft,
    _majority_explicit_length,
    normalize_type,
    parse_document_text,
)


def number(value: object) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value).strip()
        if "," in text:
            return float(text.replace(".", "").replace(",", "."))
        return float(text)
    except ValueError:
        return None


def latest_cache() -> Path:
    root = Path(os.environ["APPDATA"]) / "WL Fechamento" / "Capturas"
    return max(root.glob("*/revisao_temporaria.json"), key=lambda path: path.stat().st_mtime)


def matching_reparse(row: dict) -> LabelDraft | None:
    raw = str(row.get("ocr_text") or "").strip()
    if not raw:
        return None
    candidates = parse_document_text(
        raw,
        message_id=str(row.get("message_id") or ""),
        message_date=str(row.get("message_date") or ""),
        source_path=str(row.get("source_path") or ""),
    )
    piece = str(row.get("piece") or "").upper().replace(" ", "")
    same_piece = [
        candidate for candidate in candidates
        if piece and candidate.piece.upper().replace(" ", "") == piece
    ]
    return same_piece[0] if same_piece else (candidates[0] if len(candidates) == 1 else None)


def strong_peer_support(rows: list[dict], row: dict, field: str) -> bool:
    peers = [
        candidate for candidate in rows
        if candidate.get("message_date") == row.get("message_date")
        and str(candidate.get("piece") or "").upper().replace(" ", "")
        == str(row.get("piece") or "").upper().replace(" ", "")
        and candidate.get(field) not in (None, "")
    ]
    values = [str(candidate.get(field)).strip().upper() for candidate in peers]
    target = str(row.get(field)).strip().upper()
    support = sum(value == target for value in values)
    return support >= 3 and support / max(1, len(values)) >= 0.75


def strong_catalog_support(rows: list[dict], row: dict, field: str) -> bool:
    peers = [
        candidate for candidate in rows
        if str(candidate.get("work") or "").strip().upper()
        == str(row.get("work") or "").strip().upper()
        and str(candidate.get("piece") or "").upper().replace(" ", "")
        == str(row.get("piece") or "").upper().replace(" ", "")
        and candidate.get(field) not in (None, "")
    ]
    values = [str(candidate.get(field)).strip().upper() for candidate in peers]
    target = str(row.get(field)).strip().upper()
    support = sum(value == target for value in values)
    return support >= 5 and support / max(1, len(values)) >= 0.85


def audit(row: dict, rows: list[dict]) -> list[str]:
    issues: list[str] = []
    product = str(row.get("product") or "").strip().upper()
    piece = str(row.get("piece") or "").strip().upper().replace(" ", "")
    section = str(row.get("section") or "").strip().upper()
    length = number(row.get("length"))
    volume = number(row.get("unit_volume"))
    raw = str(row.get("ocr_text") or "")

    expected_product = ""
    prefix_match = re.match(r"[A-Z]+", piece)
    prefix = prefix_match.group(0) if prefix_match else ""
    if prefix in {"PH", "PP"}:
        expected_product = "PILAR"
    elif prefix == "PM":
        expected_product = "PAINEL"
    elif prefix in {"VPT", "VPR", "VRT", "VCR", "VOL", "VL", "VR", "VP"}:
        expected_product = "VIGA"
    if expected_product and product != expected_product:
        issues.append(f"produto {product!r} conflita com prefixo {prefix}")

    if product == "PAINEL" and section and not (section.startswith("E=") or "X" in section):
        issues.append(f"seção de painel fora do padrão: {section}")
    if product in {"PILAR", "VIGA"} and section and "X" not in section and section != "VARIAVEL":
        issues.append(f"seção de {product.lower()} fora do padrão: {section}")
    if length is not None and not 0 < length <= 30:
        issues.append(f"comprimento fora do intervalo: {length}")
    if volume is not None and not 0 < volume <= 10:
        issues.append(f"volume fora do intervalo: {volume}")
    if length is not None and volume is not None and abs(length - volume) < 0.0005:
        issues.append("comprimento e volume são o mesmo número")

    expected_type = normalize_type(str(row.get("work") or ""), product, length)
    if product and str(row.get("type_name") or "") != expected_type:
        issues.append(
            f"tipo salvo {row.get('type_name')!r} difere do calculado {expected_type!r}"
        )

    majority_length = _majority_explicit_length(raw)
    if majority_length and length is not None:
        majority_value = number(majority_length)
        if majority_value is not None and abs(majority_value - length) >= 0.0005:
            issues.append(f"maioria OCR do comprimento é {majority_length}, salvo {row.get('length')}")

    reparsed = matching_reparse(row)
    if reparsed is not None:
        reparsed_length = number(reparsed.length)
        if (
            reparsed_length is not None
            and length is not None
            and abs(reparsed_length - length) >= 0.0005
            and not strong_peer_support(rows, row, "length")
            and not strong_catalog_support(rows, row, "length")
        ):
            issues.append(f"parser atual lê comprimento {reparsed.length}, salvo {row.get('length')}")
        reparsed_volume = number(reparsed.unit_volume)
        if (
            reparsed_volume is not None
            and volume is not None
            and abs(reparsed_volume - volume) >= 0.0005
            and not strong_peer_support(rows, row, "unit_volume")
            and not strong_catalog_support(rows, row, "unit_volume")
        ):
            issues.append(f"parser atual lê volume {reparsed.unit_volume}, salvo {row.get('unit_volume')}")

    weights = [
        number(token)
        for token in re.findall(r"(?i)\bpeso\s*(?:\([^)]*\))?\s*[:.]?\s*(\d{3,6}[.,]\d{2})", raw)
    ]
    weights = [value for value in weights if value is not None and value > 100]
    if weights and volume is not None:
        weight, weight_support = Counter(round(value, 2) for value in weights).most_common(1)[0]
        density = weight / volume
        if weight_support >= 2 and not 1800 <= density <= 3000:
            issues.append(f"densidade incompatível: {density:.0f} kg/m³")

    work = str(row.get("work") or "")
    if re.search(r"(?i)\b(?:sigla|produto|se[cç][aã]o|comprimento|peso|pe[cç]a|vol)\b", work):
        issues.append("obra contém rótulos de outros campos")
    return list(dict.fromkeys(issues))


def main() -> None:
    source = latest_cache()
    loaded = json.loads(source.read_text(encoding="utf-8"))
    rows = [item for values in loaded.values() for item in values if isinstance(item, dict)]
    automatic = [row for row in rows if not row.get("warnings")]
    suspicious = []
    for index, row in enumerate(rows, start=1):
        if row.get("warnings"):
            continue
        issues = audit(row, rows)
        if issues:
            suspicious.append({
                "index": index,
                "piece": row.get("piece"),
                "date": row.get("message_date"),
                "issues": issues,
                "source_path": row.get("source_path"),
            })
    print(json.dumps({
        "cache": str(source),
        "total": len(rows),
        "automatic": len(automatic),
        "pending": len(rows) - len(automatic),
        "suspicious_automatic": len(suspicious),
        "suspicious": suspicious,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
