from __future__ import annotations

import json
import hashlib
import re
import unicodedata
from dataclasses import asdict
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

from .label_parser import LabelDraft, normalize_type, parse_document_text
from .config import configuration_directory
from .ocr_service import read_image_texts
from .paddle_ocr_service import is_available as paddle_available
from .paddle_ocr_service import LayoutLine
from .pdf_evidence_service import render_pdf_pages
from .stake_parser import parse_stake_text
from .vision_service import (
    VISION_PIPELINE_VERSION,
    VisionAnalysis,
    analyze_image,
    apply_group_context,
    decide_fields,
    enrich_isolated_fields_batch,
)
from .whatsapp_service import WhatsAppProbeResult
from .whatsapp_service import WhatsAppAttachment


ProgressCallback = Callable[[int, int, str], None]


def _sanitize_duplicate_measurements(draft: LabelDraft) -> None:
    """Undo an OCR token assigned to both length and unit volume.

    Keep the value only in the field whose printed label is directly visible
    in the raw OCR.  If neither side is demonstrable, clear both.  Consensus
    or a later accurate OCR pass may then fill the missing field safely.
    """
    if not draft.length or draft.unit_volume is None:
        return
    try:
        length = float(draft.length.replace(".", "").replace(",", "."))
    except ValueError:
        return
    if abs(length - float(draft.unit_volume)) >= 0.0005:
        return
    raw = draft.ocr_text or ""
    target = re.escape(draft.length).replace(",", "[.,]").replace("\\.", "[.,]")
    length_evidence = bool(re.search(
        rf"(?is)\bcom\w*[^0-9]{{0,4}}(?:\([^)]*\))?[^0-9]{{0,4}}{target}", raw
    ))
    volume_evidence = bool(re.search(
        rf"(?is)\bvol\w*[^0-9]{{0,4}}(?:\([^)]*\))?[^0-9]{{0,4}}{target}", raw
    ))
    if length_evidence and not volume_evidence:
        draft.unit_volume = None
        if "Confirmar volume unitário" not in draft.warnings:
            draft.warnings.append("Confirmar volume unitário")
    elif volume_evidence and not length_evidence:
        draft.length = ""
        if "Confirmar comprimento" not in draft.warnings:
            draft.warnings.append("Confirmar comprimento")
    else:
        draft.length = ""
        draft.unit_volume = None
        for warning in ("Confirmar comprimento", "Confirmar volume unitário"):
            if warning not in draft.warnings:
                draft.warnings.append(warning)


def _apply_message_consensus(drafts: list[LabelDraft]) -> None:
    """Fill only invariant fields shared by every readable label in a message.

    An album can contain different pieces, dimensions and volumes, so those
    fields are never copied.  Work and base product are copied only when at
    least two readable labels agree and no readable label disagrees.
    """
    for draft in drafts:
        _sanitize_duplicate_measurements(draft)

    groups: dict[str, list[LabelDraft]] = defaultdict(list)
    for draft in drafts:
        groups[draft.message_id.split(":linha-", 1)[0]].append(draft)
    for group in groups.values():
        if len(group) < 2:
            continue
        for field_name in ("work", "product"):
            observed = {
                str(getattr(draft, field_name)).strip()
                for draft in group
                if str(getattr(draft, field_name)).strip()
            }
            if len(observed) != 1 or sum(bool(str(getattr(draft, field_name)).strip()) for draft in group) < 2:
                continue
            agreed = next(iter(observed))
            for draft in group:
                if not str(getattr(draft, field_name)).strip():
                    setattr(draft, field_name, agreed)
        for draft in group:
            try:
                length = float(draft.length.replace(".", "").replace(",", ".")) if draft.length else None
            except ValueError:
                length = None
            if not draft.type_name:
                draft.type_name = normalize_type(draft.work, draft.product, length)
            resolved = {
                "Confirmar obra": bool(draft.work),
                "Confirmar produto": bool(draft.product),
                "Confirmar tipo normalizado": bool(draft.type_name),
            }
            draft.warnings = [warning for warning in draft.warnings if not resolved.get(warning, False)]
            draft.status = "PRONTO PARA REVISÃO" if not draft.warnings else "CONFIRMAR"

    # The same piece code on the same day may appear in several photos.  Fill
    # a missing field only when every readable occurrence agrees and at least
    # two independent readings support that exact value.  Conflicts are left
    # pending, which preserves the user's rule that grouping requires all
    # information to be identical.
    repeated: dict[tuple[str, str], list[LabelDraft]] = defaultdict(list)
    for draft in drafts:
        piece_key = str(draft.piece).strip().upper().replace(" ", "")
        if piece_key and draft.message_date:
            repeated[(draft.message_date, piece_key)].append(draft)
    for group in repeated.values():
        if len(group) < 2:
            continue
        for field_name in ("work", "product", "section", "length", "unit_volume"):
            observed = [getattr(draft, field_name) for draft in group if getattr(draft, field_name) not in ("", None)]
            canonical = {str(value).strip().upper() for value in observed}
            if len(observed) < 2 or len(canonical) != 1:
                continue
            agreed = observed[0]
            for draft in group:
                if getattr(draft, field_name) in ("", None):
                    setattr(draft, field_name, agreed)
        for draft in group:
            try:
                length = float(draft.length.replace(".", "").replace(",", ".")) if draft.length else None
            except ValueError:
                length = None
            draft.type_name = draft.type_name or normalize_type(draft.work, draft.product, length)
            draft.dimensions = " ".join(item for item in (draft.section, draft.length) if item)
            resolved = {
                "Confirmar obra": bool(draft.work),
                "Confirmar produto": bool(draft.product),
                "Confirmar peça": bool(draft.piece),
                "Confirmar seção": bool(draft.section),
                "Confirmar comprimento": bool(draft.length),
                "Confirmar volume unitário": draft.unit_volume is not None,
                "Confirmar tipo normalizado": bool(draft.type_name),
            }
            draft.warnings = [warning for warning in draft.warnings if not resolved.get(warning, False)]
            draft.status = "PRONTO PARA REVISÃO" if not draft.warnings else "CONFIRMAR"

    # OCR occasionally swaps a clearly printed length with the nearby volume
    # in one photo.  For the same piece on the same day, allow a strong
    # majority to fill a *missing* value even when one isolated reading is
    # noisy.  Existing values are never overwritten.  Requiring three
    # readings and at least 75% agreement keeps this a conservative recovery,
    # not a guess.
    for group in repeated.values():
        if len(group) < 3:
            continue
        for field_name in ("work", "product", "section", "length", "unit_volume"):
            observed: list[object] = []
            for draft in group:
                value = getattr(draft, field_name)
                if value in ("", None):
                    continue
                if field_name == "length" and draft.unit_volume is not None:
                    try:
                        parsed_length = float(str(value).replace(".", "").replace(",", "."))
                    except ValueError:
                        parsed_length = None
                    if parsed_length is not None and abs(parsed_length - float(draft.unit_volume)) < 0.0005:
                        continue
                observed.append(value)
            if len(observed) < 3:
                continue
            keyed = [str(value).strip().upper() for value in observed]
            agreed_key, support = Counter(keyed).most_common(1)[0]
            if support < 3 or support / len(observed) < 0.75:
                continue
            agreed = next(value for value in observed if str(value).strip().upper() == agreed_key)
            for draft in group:
                if getattr(draft, field_name) in ("", None):
                    setattr(draft, field_name, agreed)

    # Build a local catalog from repeated, conflict-free readings. This is
    # stronger than OCR guessing: a field is learned only when the same work
    # and piece produced the identical value at least twice.
    catalog: dict[tuple[str, str], list[LabelDraft]] = defaultdict(list)
    for draft in drafts:
        work_key = str(draft.work).strip().upper()
        piece_key = str(draft.piece).strip().upper().replace(" ", "")
        if work_key and piece_key:
            catalog[(work_key, piece_key)].append(draft)
    for group in catalog.values():
        for field_name in ("product", "section", "length", "unit_volume"):
            observed = [getattr(draft, field_name) for draft in group if getattr(draft, field_name) not in ("", None)]
            canonical = {str(value).strip().upper() for value in observed}
            if len(observed) < 2 or len(canonical) != 1:
                continue
            agreed = observed[0]
            for draft in group:
                if getattr(draft, field_name) in ("", None):
                    setattr(draft, field_name, agreed)

    # A stable piece catalogue may span different message dates.  Permit one
    # isolated OCR distortion only with substantial evidence: at least five
    # matching readings and 85% agreement.  This still fills missing fields
    # only and never changes a populated value.
    for group in catalog.values():
        for field_name in ("product", "section", "length", "unit_volume"):
            observed = [
                getattr(draft, field_name)
                for draft in group
                if getattr(draft, field_name) not in ("", None)
            ]
            if len(observed) < 5:
                continue
            keyed = [str(value).strip().upper() for value in observed]
            agreed_key, support = Counter(keyed).most_common(1)[0]
            if support < 5 or support / len(observed) < 0.85:
                continue
            agreed = next(value for value in observed if str(value).strip().upper() == agreed_key)
            for draft in group:
                if getattr(draft, field_name) in ("", None):
                    setattr(draft, field_name, agreed)

    # Some code families have an invariant section in a given work/product.
    # Learn it only from at least three independent complete readings and
    # only when there is no conflicting section anywhere in that family.
    family_catalog: dict[tuple[str, str, str], list[LabelDraft]] = defaultdict(list)
    for draft in drafts:
        prefix = "".join(character for character in draft.piece.upper() if character.isalpha())
        if draft.work and draft.product and prefix:
            family_catalog[(draft.work.strip().upper(), draft.product.strip().upper(), prefix)].append(draft)
    for group in family_catalog.values():
        observed = [draft.section for draft in group if draft.section]
        canonical = {value.strip().upper() for value in observed}
        if len(observed) < 3 or len(canonical) != 1:
            continue
        agreed = observed[0]
        for draft in group:
            if not draft.section:
                draft.section = agreed

    # Recover a missing section from an otherwise identical, repeatedly
    # observed fingerprint. This is useful when glare hides only `E=8`.
    section_fingerprints: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    for draft in drafts:
        volume_key = "" if draft.unit_volume is None else f"{draft.unit_volume:.6f}"
        if all((draft.work, draft.product, draft.length, volume_key, draft.section)):
            section_fingerprints[(
                draft.work.strip().upper(), draft.product.strip().upper(),
                draft.length.strip(), volume_key,
            )].append(draft.section)
    for draft in drafts:
        volume_key = "" if draft.unit_volume is None else f"{draft.unit_volume:.6f}"
        if not draft.section and all((draft.work, draft.product, draft.length, volume_key)):
            values = section_fingerprints.get((
                draft.work.strip().upper(), draft.product.strip().upper(),
                draft.length.strip(), volume_key,
            ), [])
            unique = {value.strip().upper() for value in values}
            if len(values) >= 2 and len(unique) == 1:
                draft.section = values[0]

    # Reverse lookup: recover a missing piece/work only when a complete
    # fingerprint occurs at least twice and maps to exactly one value.
    piece_fingerprints: dict[tuple[str, str, str, str, str], list[str]] = defaultdict(list)
    work_fingerprints: dict[tuple[str, str, str, str, str], list[str]] = defaultdict(list)
    for draft in drafts:
        volume_key = "" if draft.unit_volume is None else f"{draft.unit_volume:.6f}"
        if all((draft.work, draft.product, draft.section, draft.length, volume_key, draft.piece)):
            piece_fingerprints[(
                draft.work.strip().upper(), draft.product.strip().upper(),
                draft.section.strip().upper(), draft.length.strip(), volume_key,
            )].append(draft.piece)
            work_fingerprints[(
                draft.product.strip().upper(), draft.piece.strip().upper().replace(" ", ""),
                draft.section.strip().upper(), draft.length.strip(), volume_key,
            )].append(draft.work)
    for draft in drafts:
        volume_key = "" if draft.unit_volume is None else f"{draft.unit_volume:.6f}"
        if not draft.piece and all((draft.work, draft.product, draft.section, draft.length, volume_key)):
            values = piece_fingerprints.get((
                draft.work.strip().upper(), draft.product.strip().upper(),
                draft.section.strip().upper(), draft.length.strip(), volume_key,
            ), [])
            unique = {value.strip().upper().replace(" ", "") for value in values}
            if len(values) >= 2 and len(unique) == 1:
                draft.piece = values[0]
        if not draft.work and all((draft.product, draft.piece, draft.section, draft.length, volume_key)):
            values = work_fingerprints.get((
                draft.product.strip().upper(), draft.piece.strip().upper().replace(" ", ""),
                draft.section.strip().upper(), draft.length.strip(), volume_key,
            ), [])
            unique = {value.strip().upper() for value in values}
            if len(values) >= 2 and len(unique) == 1:
                draft.work = values[0]

    # A single OCR-confused code must not block a well-supported reverse
    # lookup (for example PM-4 read once as PM-14).  Use a strong majority
    # only to fill empty piece/work fields; never replace a populated field.
    for draft in drafts:
        volume_key = "" if draft.unit_volume is None else f"{draft.unit_volume:.6f}"
        if not draft.piece and all((draft.work, draft.product, draft.section, draft.length, volume_key)):
            values = piece_fingerprints.get((
                draft.work.strip().upper(), draft.product.strip().upper(),
                draft.section.strip().upper(), draft.length.strip(), volume_key,
            ), [])
            counts = Counter(value.strip().upper().replace(" ", "") for value in values)
            if values and counts:
                agreed_key, support = counts.most_common(1)[0]
                if support >= 3 and support / len(values) >= 0.75:
                    draft.piece = next(
                        value for value in values
                        if value.strip().upper().replace(" ", "") == agreed_key
                    )

    # Recalculate all derived fields and remove only warnings whose source
    # field is now demonstrably present.
    for draft in drafts:
        try:
            length = float(draft.length.replace(".", "").replace(",", ".")) if draft.length else None
        except ValueError:
            length = None
        draft.type_name = normalize_type(draft.work, draft.product, length) if draft.product else ""
        if draft.type_name:
            draft.product = draft.type_name
        draft.dimensions = " ".join(item for item in (draft.section, draft.length) if item)
        resolved = {
            "Confirmar obra": bool(draft.work),
            "Confirmar produto": bool(draft.product),
            "Confirmar peça": bool(draft.piece),
            "Confirmar seção": bool(draft.section),
            "Confirmar comprimento": bool(draft.length),
            "Confirmar volume unitário": draft.unit_volume is not None,
            "Confirmar tipo normalizado": bool(draft.type_name),
        }
        draft.warnings = [warning for warning in draft.warnings if not resolved.get(warning, False)]
        draft.status = "PRONTO PARA REVISÃO" if not draft.warnings else "CONFIRMAR"


def _message_date(result: WhatsAppProbeResult, message_id: str) -> str:
    for evidence in result.evidences:
        if message_id == evidence.message_id or message_id.startswith(f"{evidence.message_id}:"):
            return evidence.message_date
        if evidence.message_id.startswith(f"{message_id}:"):
            return evidence.message_date
    return ""


def _message_quantity(
    result: WhatsAppProbeResult,
    message_id: str,
) -> int | float | None:
    for evidence in result.evidences:
        if (
            message_id == evidence.message_id
            or message_id.startswith(f"{evidence.message_id}:")
            or evidence.message_id.startswith(f"{message_id}:")
        ):
            return evidence.quantity_hint
    return None


def _apply_message_quantity(
    drafts: list[LabelDraft],
    result: WhatsAppProbeResult,
    message_id: str,
) -> None:
    quantity = _message_quantity(result, message_id)
    if quantity is None:
        return
    # A caption belongs to the message/album, not automatically to every
    # photo or every table row. Only one logical row has an unambiguous scope.
    candidates = [draft for draft in drafts if draft.quantity == 1]
    if len(drafts) == 1 and len(candidates) == 1:
        candidates[0].quantity = quantity
        return
    if candidates:
        warning = "Confirmar alcance da quantidade da mensagem"
        for draft in candidates:
            if warning not in draft.warnings:
                draft.warnings.append(warning)
            draft.status = "CONFIRMAR"


def _record_id(message_id: str, attachment_hash: str, row_index: int) -> str:
    raw = f"{message_id}\0{attachment_hash}\0{row_index}".encode("utf-8")
    return "wl-" + hashlib.sha256(raw).hexdigest()[:24]


def _load_review_rows(cache_path: Path) -> dict[str, dict]:
    if not cache_path.exists():
        return {}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    rows: dict[str, dict] = {}
    if not isinstance(payload, dict):
        return rows
    for group in payload.values():
        if not isinstance(group, list):
            continue
        for index, item in enumerate(group):
            if not isinstance(item, dict):
                continue
            identity = str(item.get("record_id") or "")
            if not identity:
                identity = (
                    f"legacy:{item.get('message_id', '')}:"
                    f"{item.get('source_path', '')}:{index}"
                )
            rows[identity] = item
    return rows


def _preserve_reviewed_values(draft: LabelDraft, previous: dict | None) -> None:
    """Keep operator decisions across OCR reprocessing.

    New caches track fields changed by the user. For legacy caches, explicit
    workflow states are treated conservatively as reviewed and preserved.
    """
    if not previous:
        return
    editable = (
        "message_date", "work", "product", "piece", "section", "length",
        "dimensions", "unit_volume", "type_name", "quantity", "cargo_type",
    )
    manual = {
        str(name) for name in previous.get("manual_fields", [])
        if str(name) in editable
    }
    previous_status = str(previous.get("status") or "").upper()
    if previous_status in {"PENDENTE", "CONFIRMADO", "APROVADO", "REJEITADO"}:
        manual.update(editable)
    for name in manual:
        if name in previous:
            setattr(draft, name, previous[name])
    draft.manual_fields = sorted(manual)
    if previous_status in {"PENDENTE", "CONFIRMADO", "APROVADO", "REJEITADO"}:
        draft.status = previous_status
        draft.warnings = [str(item) for item in previous.get("warnings", [])]


def _stake_text_drafts(result: WhatsAppProbeResult, source_path: str) -> list[LabelDraft]:
    drafts: list[LabelDraft] = []
    for evidence in result.evidences:
        if not evidence.stake_text:
            continue
        try:
            entry = parse_stake_text(evidence.stake_text)
        except ValueError:
            continue
        warnings = [] if evidence.message_date else ["Confirmar data da mensagem"]
        warnings.append("Confirmar obra")
        drafts.append(LabelDraft(
            message_id=evidence.message_id,
            message_date=evidence.message_date,
            source_path=source_path,
            product=entry.type_name,
            type_name=entry.type_name,
            piece=entry.piece,
            dimensions=entry.dimensions,
            unit_volume=entry.unit_volume,
            quantity=entry.quantity,
            status="CONFIRMAR",
            warnings=warnings,
            ocr_text=evidence.message_text or evidence.stake_text,
            record_id=_record_id(evidence.message_id, "texto-estaca", 0),
        ))
    return drafts


def _vision_analysis_to_draft(
    analysis: VisionAnalysis,
    result: WhatsAppProbeResult,
    message_id: str,
) -> LabelDraft:
    """Convert audited field decisions into the existing review format."""
    values = {
        name: decision.value
        for name, decision in analysis.fields.items()
    }
    warnings = [
        f"Confirmar {decision.label}"
        for decision in analysis.fields.values()
        if decision.status != "CONFIRMADO_AUTOMATICAMENTE"
    ]
    length = str(values.get("length") or "")
    unit_volume = values.get("unit_volume")
    try:
        parsed_volume = float(unit_volume) if unit_volume not in (None, "") else None
    except (TypeError, ValueError):
        parsed_volume = None
    draft = LabelDraft(
        message_id=message_id,
        message_date=_message_date(result, message_id),
        source_path=analysis.source_path,
        work=str(values.get("work") or ""),
        product=analysis.product_type or str(values.get("product") or ""),
        type_name=analysis.product_type,
        piece=str(values.get("piece") or ""),
        section=str(values.get("section") or ""),
        length=length,
        dimensions=" ".join(
            item for item in (str(values.get("section") or ""), length) if item
        ),
        unit_volume=parsed_volume,
        status="PRONTO PARA REVISÃO" if not warnings else "CONFIRMAR",
        warnings=warnings,
        ocr_text="\n\n".join(
            reading.text for reading in analysis.readings
            if not reading.field_hint and reading.text
        ),
    )
    _apply_message_quantity([draft], result, message_id)
    return draft


def _structured_document_drafts(
    analysis: VisionAnalysis,
    result: WhatsAppProbeResult,
    message_id: str,
) -> list[LabelDraft]:
    """Keep multi-row delivery notes that cannot be represented by one label."""
    layout_drafts = _stake_delivery_layout_drafts(
        analysis.layout_lines, result, message_id, analysis.source_path
    )
    if layout_drafts:
        _apply_message_quantity(layout_drafts, result, message_id)
        return layout_drafts
    alternatives: list[list[LabelDraft]] = []
    for reading in analysis.readings:
        if reading.field_hint or not reading.text:
            continue
        parsed = parse_document_text(
            reading.text,
            message_id=message_id,
            message_date=_message_date(result, message_id),
            source_path=analysis.source_path,
        )
        plain_text = reading.text.upper()
        is_stake_delivery = (
            len(parsed) == 1
            and parsed[0].product == "ESTACA"
            and "QUANTIDADE" in plain_text
            and "METROS" in plain_text
        )
        if len(parsed) > 1 or is_stake_delivery:
            _apply_message_quantity(parsed, result, message_id)
            alternatives.append(parsed)
    return max(alternatives, key=len) if alternatives else []


def _layout_plain(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value or "")
    return "".join(
        character for character in decomposed
        if not unicodedata.combining(character)
    ).upper().strip()


def _layout_center(line: LayoutLine) -> tuple[float, float]:
    return ((line.left + line.right) / 2, (line.top + line.bottom) / 2)


def _stake_delivery_layout_drafts(
    lines: list[LayoutLine],
    result: WhatsAppProbeResult,
    message_id: str,
    source_path: str,
) -> list[LabelDraft]:
    """Reconstruct stake rows from OCR coordinates instead of flattened text.

    Delivery notes are tables. Pairing numbers by text order can put quantity,
    length and metres in the wrong fields. Here each cell is assigned to the
    printed column and to the nearest physical row. Equal dimensions are then
    consolidated by summing the printed ``Metros`` cells, which is the value
    charged in the workbook.
    """
    if not lines:
        return []
    header_aliases = {
        "piece": ("PECA",),
        "dimension": ("DIMENSAO",),
        "quantity": ("QUANTIDADE",),
        "length": ("COMPRIMENTO",),
        "meters": ("METROS",),
        "weight": ("PESO",),
    }
    headers: dict[str, LayoutLine] = {}
    for name, aliases in header_aliases.items():
        candidates = [
            line for line in lines
            if any(alias in _layout_plain(line.text) for alias in aliases)
        ]
        if candidates:
            headers[name] = min(candidates, key=lambda line: line.top)
    if set(headers) != set(header_aliases):
        return []

    ordered = sorted(
        ((name, _layout_center(line)[0]) for name, line in headers.items()),
        key=lambda item: item[1],
    )
    if [name for name, _ in ordered] != [
        "piece", "dimension", "quantity", "length", "meters", "weight"
    ]:
        return []
    bounds: dict[str, tuple[float, float]] = {}
    for index, (name, center) in enumerate(ordered):
        left = -float("inf") if index == 0 else (ordered[index - 1][1] + center) / 2
        right = float("inf") if index == len(ordered) - 1 else (center + ordered[index + 1][1]) / 2
        bounds[name] = (left, right)

    table_top = max(line.bottom for line in headers.values())
    columns: dict[str, list[LayoutLine]] = {name: [] for name in headers}
    for line in lines:
        x, y = _layout_center(line)
        if y <= table_top + 4:
            continue
        for name, (left, right) in bounds.items():
            if left <= x < right:
                columns[name].append(line)
                break

    anchors = [
        line for line in columns["piece"]
        if re.fullmatch(r"E?STACA", _layout_plain(line.text).replace(" ", ""))
    ]
    if not anchors:
        return []
    anchors.sort(key=lambda line: _layout_center(line)[1])

    def nearest(column: str, y: float) -> LayoutLine | None:
        candidates = sorted(
            columns[column], key=lambda line: abs(_layout_center(line)[1] - y)
        )
        if not candidates:
            return None
        candidate = candidates[0]
        return candidate if abs(_layout_center(candidate)[1] - y) <= 32 else None

    parsed_rows: list[tuple[str, int]] = []
    for anchor in anchors:
        y = _layout_center(anchor)[1]
        dimension_line = nearest("dimension", y)
        meters_line = nearest("meters", y)
        if not dimension_line or not meters_line:
            continue
        dimension_match = re.search(
            r"\b\d{1,3}\s*[X×]\s*\d{1,3}\b", _layout_plain(dimension_line.text)
        )
        meters_match = re.fullmatch(r"\s*(\d{1,4})\s*", meters_line.text)
        if not dimension_match or not meters_match:
            continue
        dimension = re.sub(r"\s*[X×]\s*", "X", dimension_match.group(0))
        meters = int(meters_match.group(1))
        if meters > 0:
            parsed_rows.append((dimension, meters))
    if not parsed_rows:
        return []

    work = ""
    work_lines = [line for line in lines if re.search(r"\bOBRA\b", _layout_plain(line.text))]
    if work_lines:
        work_label = min(work_lines, key=lambda line: line.top)
        first = re.sub(r"(?i)^.*?OBRA\s*:?\s*", "", work_label.text).strip()
        parts = [first] if first else []
        equipment_headers = [
            line.top for line in lines
            if line.top > work_label.top and any(
                marker in _layout_plain(line.text)
                for marker in ("CAMINHAO", "CARRETA", "MOTORISTA", "INICIO", "OCULTAR", "CHEGADA")
            )
        ]
        next_header_top = min(equipment_headers) if equipment_headers else min(
            line.top for line in headers.values()
        )
        for line in sorted(lines, key=lambda item: item.top):
            if (
                line is not work_label
                and line.top >= work_label.bottom
                and line.top < next_header_top
                and abs(line.left - work_label.left) <= 80
                and len(_layout_plain(line.text)) >= 3
            ):
                plain = _layout_plain(line.text)
                if not any(marker in plain for marker in (
                    "CAMINHAO", "CARRETA", "MOTORISTA", "INICIO", "OCULTAR", "CHEGADA"
                )):
                    parts.append(line.text.strip())
        work = " ".join(parts).strip()

    grouped: dict[str, int] = defaultdict(int)
    for dimension, meters in parsed_rows:
        grouped[dimension] += meters
    message_date = _message_date(result, message_id)
    drafts: list[LabelDraft] = []
    audit_text = "\n".join(line.text for line in sorted(lines, key=lambda line: (line.top, line.left)))
    for dimension, total_meters in grouped.items():
        warnings: list[str] = []
        if not work:
            warnings.append("Confirmar obra")
        if not message_date:
            warnings.append("Confirmar data da mensagem")
        drafts.append(LabelDraft(
            message_id=message_id,
            message_date=message_date,
            source_path=source_path,
            work=work,
            product="ESTACA",
            type_name="ESTACA",
            piece=dimension,
            section=dimension,
            length="",
            dimensions=dimension,
            unit_volume=None,
            quantity=total_meters,
            status="PRONTO PARA REVISÃO" if not warnings else "CONFIRMAR",
            warnings=warnings,
            ocr_text=audit_text,
        ))
    return drafts


def build_advanced_review_drafts(
    result: WhatsAppProbeResult,
    progress: ProgressCallback | None = None,
) -> list[LabelDraft]:
    """Run the auditable per-field visual pipeline used by the main app.

    Every expensive photo result is cached separately and can be resumed.
    The workbook and WhatsApp are never modified here.
    """
    images = [
        attachment for attachment in result.captured_attachments
        if attachment.mime_type.lower().startswith("image/")
    ]
    pdfs = [
        attachment for attachment in result.captured_attachments
        if attachment.mime_type.lower() == "application/pdf"
        or attachment.filename.lower().endswith(".pdf")
    ]
    has_non_media_evidence = any(
        evidence.stake_text or evidence.pdf_names for evidence in result.evidences
    )
    if not images and not pdfs and not has_non_media_evidence:
        return []
    if images or pdfs:
        capture_dir = Path((images or pdfs)[0].path).parent
    else:
        identity = hashlib.sha256("|".join(
            evidence.message_id for evidence in result.evidences
        ).encode("utf-8")).hexdigest()[:16]
        capture_dir = configuration_directory() / "Capturas" / f"texto_{identity}"
        capture_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir = capture_dir / "analise_visual_v2"
    evidence_dir = analysis_dir / "evidencias"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    for pdf in pdfs:
        try:
            pages = render_pdf_pages(Path(pdf.path), analysis_dir / "paginas_pdf")
        except Exception:
            continue
        for page_index, page in enumerate(pages, start=1):
            page_hash = hashlib.sha256(page.read_bytes()).hexdigest()
            images.append(WhatsAppAttachment(
                message_id=f"{pdf.message_id}:pdf-pagina-{page_index}",
                filename=f"{pdf.filename} - página {page_index}",
                mime_type="image/png", path=str(page), size=page.stat().st_size,
                sha256=page_hash,
            ))
    processed: list[tuple[object, VisionAnalysis, Path]] = []
    failures: dict[str, str] = {}
    total = len(images)
    for index, attachment in enumerate(images, start=1):
        if progress:
            progress(index, total, attachment.filename)
        cache_name = f"{attachment.sha256 or Path(attachment.path).stem}.json"
        analysis_path = analysis_dir / cache_name
        analysis: VisionAnalysis | None = None
        if analysis_path.exists():
            try:
                payload = json.loads(analysis_path.read_text(encoding="utf-8"))
                if (
                    str(payload.get("source_path") or "") == attachment.path
                    # Version 8 preserves the complete geometry of romaneios.
                    # readings must be regenerated to avoid field swaps.
                    and int(payload.get("pipeline_version") or 0) >= 8
                ):
                    analysis = VisionAnalysis.from_dict(payload)
            except (OSError, json.JSONDecodeError, KeyError, TypeError):
                analysis = None
        if analysis is None:
            try:
                analysis = analyze_image(Path(attachment.path), evidence_dir)
                analysis.save(analysis_path)
            except Exception as exc:
                # One damaged file must not discard the rest of the batch.
                failures[attachment.path] = str(exc)
                analysis = VisionAnalysis(
                    source_path=attachment.path,
                    label_crop_path="",
                    fields=decide_fields([]),
                    readings=[],
                )
        processed.append((attachment, analysis, analysis_path))

    analyses = [analysis for _, analysis, _ in processed]
    enrich_isolated_fields_batch(analyses)
    apply_group_context(analyses)
    cache_path = capture_dir / "revisao_temporaria.json"
    previous_rows = _load_review_rows(cache_path)
    drafts: list[LabelDraft] = []
    review_cache: dict[str, list[dict]] = {}
    cache_key_by_path: dict[str, str] = {}
    for attachment, analysis, analysis_path in processed:
        if attachment.path not in failures:
            analysis.save(analysis_path)
        image_drafts = _structured_document_drafts(
            analysis, result, attachment.message_id
        )
        if not image_drafts:
            image_drafts = [
                _vision_analysis_to_draft(analysis, result, attachment.message_id)
            ]
        for row_index, draft in enumerate(image_drafts):
            draft.record_id = _record_id(
                attachment.message_id, attachment.sha256 or attachment.path, row_index
            )
            previous = previous_rows.get(draft.record_id)
            if previous is None:
                previous = previous_rows.get(
                    f"legacy:{draft.message_id}:{draft.source_path}:{row_index}"
                )
            _preserve_reviewed_values(draft, previous)
        if attachment.path in failures:
            for draft in image_drafts:
                draft.warnings.insert(
                    0, f"Não foi possível ler a foto: {failures[attachment.path]}"
                )
                draft.status = "CONFIRMAR"
        drafts.extend(image_drafts)
        cache_key = f"{attachment.message_id}:{attachment.sha256}"
        cache_key_by_path[attachment.path] = cache_key

    # Textual stake entries are first-class evidence and do not pass through
    # OCR. They remain pending only for information the message did not prove.
    snapshot_path = capture_dir / "sessao_whatsapp.json"
    for draft in _stake_text_drafts(result, str(snapshot_path)):
        _preserve_reviewed_values(draft, previous_rows.get(draft.record_id))
        drafts.append(draft)

    captured_pdf_ids = {pdf.message_id for pdf in pdfs}
    for evidence in result.evidences:
        if not evidence.pdf_names or evidence.message_id in captured_pdf_ids:
            continue
        for pdf_index, pdf_name in enumerate(evidence.pdf_names):
            drafts.append(LabelDraft(
                message_id=evidence.message_id,
                message_date=evidence.message_date,
                source_path=str(snapshot_path),
                status="PENDENTE",
                warnings=[f"PDF não foi copiado: {pdf_name}"],
                ocr_text=evidence.message_text,
                record_id=_record_id(evidence.message_id, "pdf-ausente", pdf_index),
            ))

    # Apply the conservative repeated-piece and message consensus already
    # used by the legacy reader. It fills only conflict-free values supported
    # by multiple photos and never overwrites a populated measurement.
    _apply_message_consensus(drafts)
    # Consensus recalculates generated statuses. Reapply explicit operator
    # decisions last so a refresh can never move a reviewed pending/approved
    # row back to an automatic state.
    for draft in drafts:
        _preserve_reviewed_values(draft, previous_rows.get(draft.record_id))
    for draft in drafts:
        cache_key = cache_key_by_path.get(draft.source_path)
        if cache_key is None and draft.record_id:
            cache_key = f"texto:{draft.message_id}"
        if cache_key:
            review_cache.setdefault(cache_key, []).append(asdict(draft))

    temporary = cache_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(review_cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(cache_path)
    return drafts


def build_review_drafts(
    result: WhatsAppProbeResult,
    progress: ProgressCallback | None = None,
    retry_ocr_errors: bool = True,
) -> list[LabelDraft]:
    images = [
        attachment for attachment in result.captured_attachments
        if attachment.mime_type.lower().startswith("image/")
    ]
    drafts: list[LabelDraft] = []
    cache_path = Path(images[0].path).parent / "revisao_temporaria.json" if images else None
    cache: dict[str, list[dict]] = {}
    if cache_path and cache_path.exists():
        try:
            loaded = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cache = loaded
        except (OSError, json.JSONDecodeError):
            cache = {}

    def save_cache() -> None:
        if cache_path is None:
            return
        temporary = cache_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(cache_path)

    total = len(images)
    for index, attachment in enumerate(images, start=1):
        if progress:
            progress(index, total, attachment.filename)
        cache_key = f"{attachment.message_id}:{attachment.sha256}"
        cached = cache.get(cache_key)
        cached_has_ocr_error = isinstance(cached, list) and any(
            any("ler a foto" in str(warning).lower() for warning in item.get("warnings", []))
            for item in cached
            if isinstance(item, dict)
        )
        cached_has_pending_fields = isinstance(cached, list) and any(
            bool(item.get("warnings"))
            for item in cached
            if isinstance(item, dict)
        )
        reuse_cached_ocr = (
            isinstance(cached, list)
            and cached
            and (not cached_has_ocr_error or not retry_ocr_errors)
            and not (paddle_available() and cached_has_pending_fields)
        )
        if reuse_cached_ocr:
            # OCR is expensive, but parsing is cheap and evolves as real label
            # distortions are discovered. Reinterpret cached raw OCR text with
            # the current parser instead of perpetuating stale pending fields.
            reparsed: list[LabelDraft] = []
            for item in cached:
                if not isinstance(item, dict):
                    continue
                raw_text = str(item.get("ocr_text") or "").strip()
                if raw_text:
                    reparsed.extend(parse_document_text(
                        raw_text,
                        message_id=attachment.message_id,
                        message_date=_message_date(result, attachment.message_id),
                        source_path=attachment.path,
                    ))
                else:
                    reparsed.append(LabelDraft(**item))
            _apply_message_quantity(reparsed, result, attachment.message_id)
            drafts.extend(reparsed)
            cache[cache_key] = [asdict(item) for item in reparsed]
            try:
                save_cache()
            except OSError:
                pass
            continue
        try:
            parsed_drafts: list[LabelDraft] = []
            for reading in read_image_texts(Path(attachment.path)):
                reading_drafts = parse_document_text(
                    reading.text,
                    message_id=attachment.message_id,
                    message_date=_message_date(result, attachment.message_id),
                    source_path=attachment.path,
                )
                _apply_message_quantity(
                    reading_drafts,
                    result,
                    attachment.message_id,
                )
                for draft in reading_drafts:
                    if reading.score < 35:
                        draft.warnings.append("Leitura da foto com baixa confiança")
                        draft.status = "CONFIRMAR"
                    drafts.append(draft)
                    parsed_drafts.append(draft)
            cache[cache_key] = [asdict(item) for item in parsed_drafts]
            try:
                save_cache()
            except OSError:
                pass
        except Exception as exc:
            failed_draft = LabelDraft(
                message_id=attachment.message_id,
                message_date=_message_date(result, attachment.message_id),
                source_path=attachment.path,
                status="CONFIRMAR",
                warnings=[f"Não foi possível ler a foto: {exc}"],
            )
            drafts.append(failed_draft)
            cache[cache_key] = [asdict(failed_draft)]
            try:
                save_cache()
            except OSError:
                pass
    _apply_message_consensus(drafts)
    return drafts
