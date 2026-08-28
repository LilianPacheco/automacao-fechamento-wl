from __future__ import annotations

from dataclasses import dataclass

from .label_parser import LabelDraft


@dataclass(frozen=True)
class ConsolidatedRow:
    type_name: str
    message_date: str
    work: str
    quantity: int | float
    piece: str
    dimensions: str
    unit_volume: float | None
    cargo_type: str
    source_count: int


def _text_key(value: str) -> str:
    return " ".join((value or "").split()).casefold()


def group_approved_drafts(drafts: list[LabelDraft]) -> list[ConsolidatedRow]:
    grouped: dict[tuple[object, ...], dict[str, object]] = {}
    for draft in drafts:
        if draft.status != "APROVADO":
            continue
        key = (
            _text_key(draft.message_date),
            _text_key(draft.type_name),
            _text_key(draft.work),
            _text_key(draft.piece),
            _text_key(draft.dimensions),
            draft.unit_volume,
            _text_key(draft.cargo_type),
        )
        if key not in grouped:
            grouped[key] = {"draft": draft, "quantity": 0, "source_count": 0}
        grouped[key]["quantity"] = float(grouped[key]["quantity"]) + draft.quantity
        grouped[key]["source_count"] = int(grouped[key]["source_count"]) + 1

    rows: list[ConsolidatedRow] = []
    for item in grouped.values():
        draft = item["draft"]
        assert isinstance(draft, LabelDraft)
        quantity = float(item["quantity"])
        rows.append(ConsolidatedRow(
            type_name=draft.type_name,
            message_date=draft.message_date,
            work=draft.work,
            quantity=int(quantity) if quantity.is_integer() else round(quantity, 3),
            piece=draft.piece,
            dimensions=draft.dimensions,
            unit_volume=draft.unit_volume,
            cargo_type=draft.cargo_type,
            source_count=int(item["source_count"]),
        ))
    return sorted(rows, key=lambda row: (
        row.message_date, row.type_name.casefold(), row.work.casefold(), row.piece.casefold()
    ))
