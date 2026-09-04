from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from difflib import SequenceMatcher
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PIL import Image

from .label_parser import (
    LabelDraft,
    _explicit_known_work,
    _fuzzy_known_work,
    _product_from_piece,
    normalize_type,
    parse_document_text,
)
from .ocr_service import (
    _orange_label_crop,
    _prepare_paddle_label,
    _read_variant,
    read_image_text,
    read_image_text_targeted,
)
from .paddle_ocr_service import (
    is_available as paddle_available,
    read_line_texts as read_paddle_line_texts,
    read_text as read_paddle_text,
)


VISION_PIPELINE_VERSION = 6

READ_FIELDS = ("work", "product", "piece", "section", "length", "unit_volume")
FIELD_LABELS = {
    "work": "obra",
    "product": "produto",
    "piece": "peça",
    "section": "seção",
    "length": "comprimento",
    "unit_volume": "volume unitário",
}
FIELD_MARKERS = {
    "work": ("obra", "sigla"),
    "product": ("produto",),
    "piece": ("peca",),
    "section": ("secao",),
    "length": ("comprimento",),
    "unit_volume": ("volume", "vol"),
}
FIELD_BANDS = {
    "work": (0.22, 0.40, 0.02, 0.98),
    "product": (0.38, 0.56, 0.02, 0.90),
    "section": (0.50, 0.64, 0.02, 0.80),
    "length": (0.58, 0.72, 0.02, 0.90),
    "unit_volume": (0.63, 0.79, 0.42, 0.99),
    "piece": (0.75, 0.92, 0.02, 0.82),
}


@dataclass(frozen=True)
class VisionReading:
    engine: str
    text: str
    confidence: float
    field_hint: str = ""


@dataclass(frozen=True)
class FieldCandidate:
    field_name: str
    value: str | float
    normalized_value: str
    engine: str
    confidence: float
    explicit_label: bool
    raw_text: str


@dataclass
class FieldDecision:
    field_name: str
    label: str
    value: str | float | None = None
    confidence: float = 0.0
    status: str = "PENDENTE"
    reason: str = "Nenhuma leitura comprovada."
    crop_path: str = ""
    candidates: list[FieldCandidate] = field(default_factory=list)


@dataclass
class VisionAnalysis:
    source_path: str
    label_crop_path: str
    fields: dict[str, FieldDecision]
    readings: list[VisionReading]
    product_type: str = ""

    @property
    def pending_fields(self) -> list[str]:
        return [
            name for name, decision in self.fields.items()
            if decision.status != "CONFIRMADO_AUTOMATICAMENTE"
        ]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["pipeline_version"] = VISION_PIPELINE_VERSION
        payload["pending_fields"] = self.pending_fields
        return payload

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def from_dict(cls, payload: dict) -> "VisionAnalysis":
        return cls(
            source_path=str(payload["source_path"]),
            label_crop_path=str(payload.get("label_crop_path") or ""),
            fields={
                name: FieldDecision(
                    **{
                        **value,
                        "candidates": [
                            FieldCandidate(**candidate)
                            for candidate in value.get("candidates", [])
                        ],
                    }
                )
                for name, value in payload["fields"].items()
            },
            readings=[VisionReading(**reading) for reading in payload.get("readings", [])],
            product_type=str(payload.get("product_type") or ""),
        )


def _plain(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    return "".join(
        character for character in text
        if not unicodedata.combining(character)
    ).lower()


def _normalized_value(field_name: str, value: object) -> str:
    if value in (None, ""):
        return ""
    if field_name == "unit_volume":
        try:
            return f"{float(value):.3f}"
        except (TypeError, ValueError):
            return ""
    return re.sub(r"\s+", " ", str(value).strip().upper())


def _has_explicit_label(field_name: str, text: str) -> bool:
    normalized = _plain(text)
    return any(
        re.search(rf"\b{re.escape(marker)}\b\s*[:.]?", normalized)
        for marker in FIELD_MARKERS[field_name]
    )


def _valid_value(field_name: str, value: object) -> bool:
    if value in (None, ""):
        return False
    text = str(value).strip().upper()
    if field_name == "product":
        return text in {
            "BLOCO", "ESTACA", "ESCADA", "MURO", "PAINEL", "PILAR",
            "VIGA", "LAJE ALVEOLAR", "METRO CÚBICO", "VIGA TERÇA",
        }
    if field_name == "piece":
        return bool(re.fullmatch(
            r"[A-Z]{1,6}[-_]?\d{1,4}[A-Z]?(?:[-_][A-Z0-9]+)*",
            text.replace(" ", ""),
        ))
    if field_name == "section":
        return bool(
            re.fullmatch(r"(?:E\s*=\s*\d{1,3}|\d{2,3}\s*X\s*\d{2,3}|VARIAVEL)", text)
        )
    if field_name == "length":
        try:
            parsed = float(text.replace(".", "").replace(",", "."))
        except ValueError:
            return False
        return 0 < parsed <= 40
    if field_name == "unit_volume":
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return False
        return 0 < parsed <= 10
    if field_name == "work":
        plain = _plain(text).upper()
        if any(marker in plain for marker in (
            "PESO", "VOLUME", "COMPRIMENTO", "PRODUTO", "SECAO", "PECA",
        )):
            return False
        return len(text) <= 100 and bool(re.search(r"[A-Z]{3}", plain))
    return len(text) <= 100


def _draft_candidates(reading: VisionReading) -> list[FieldCandidate]:
    if reading.field_hint:
        value = _field_crop_value(reading.field_hint, reading.text)
        normalized = _normalized_value(reading.field_hint, value)
        if not normalized or not _valid_value(reading.field_hint, value):
            return []
        return [FieldCandidate(
            field_name=reading.field_hint,
            value=value,
            normalized_value=normalized,
            engine=reading.engine,
            confidence=max(0.0, min(1.0, reading.confidence)),
            # The crop location itself identifies the field even if one or
            # two letters of the printed label were lost by recognition.
            explicit_label=True,
            raw_text=reading.text,
        )]
    drafts = parse_document_text(reading.text)
    candidates: list[FieldCandidate] = []
    for draft in drafts:
        for field_name in READ_FIELDS:
            value = getattr(draft, field_name)
            if field_name == "work" and value:
                value = _explicit_known_work(str(value)) or _fuzzy_known_work(str(value)) or value
            normalized = _normalized_value(field_name, value)
            if not normalized or not _valid_value(field_name, value):
                continue
            candidates.append(FieldCandidate(
                field_name=field_name,
                value=value,
                normalized_value=normalized,
                engine=reading.engine,
                confidence=max(0.0, min(1.0, reading.confidence)),
                explicit_label=_has_explicit_label(field_name, reading.text),
                raw_text=reading.text,
            ))
    return candidates


def _decimal_tokens(text: str) -> list[tuple[str, float]]:
    tokens: list[tuple[str, float]] = []
    for match in re.finditer(r"(?<!\d)(\d{1,2}[.,]\d{3})", text):
        token = match.group(1)
        try:
            value = float(token.replace(",", "."))
        except ValueError:
            continue
        tokens.append((token.replace(".", ","), value))
    return tokens


def _field_crop_value(field_name: str, text: str) -> str | float | None:
    upper = str(text or "").upper()
    if field_name == "work":
        cleaned = re.sub(r"^.*?\bOBRA\s*[:.]?\s*", "", upper, count=1)
        cleaned = re.split(r"\b(?:SIGLA|PRODUTO)\b", cleaned, maxsplit=1)[0]
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" :-|.")
        canonical = _explicit_known_work(cleaned) or _fuzzy_known_work(cleaned)
        cleaned = canonical or cleaned
        return cleaned if 3 <= len(cleaned) <= 100 else None
    if field_name == "section":
        match = re.search(r"\b(E\s*=\s*\d{1,3}|\d{1,3}\s*[X×]\s*\d{1,3})", upper)
        return re.sub(r"\s+", "", match.group(1)).replace("×", "X") if match else None
    if field_name == "length":
        plausible = [token for token, value in _decimal_tokens(upper) if 0 < value <= 40]
        return plausible[0] if plausible else None
    if field_name == "unit_volume":
        plausible = [value for _, value in _decimal_tokens(upper) if 0 < value <= 10]
        return plausible[-1] if plausible else None
    if field_name == "piece":
        cleaned = re.sub(r"^.*?\bPE[CÇ]A\s*[:.]?\s*", "", upper, count=1)
        matches = re.findall(
            r"\b(?:PL|PM|VPT|VPR|VRT|VCR|VOL|VL|VR|VP|PP|PH|PA|MA|BL|EP)"
            r"[-_ ]?\d{1,4}[A-Z]?(?:[-_ ][A-Z0-9]+)?\b",
            cleaned,
        )
        if matches:
            return re.sub(r"\s+", "", matches[0]).replace("_", "-")
        return None
    if field_name == "product":
        normalized = _plain(upper).upper()
        products = (
            "LAJE ALVEOLAR", "VIGA TERCA", "METRO CUBICO", "BLOCO",
            "ESTACA", "ESCADA", "MURO", "PAINEL", "PILAR", "VIGA",
        )
        for product in products:
            if product in normalized:
                return product.replace("TERCA", "TERÇA").replace("CUBICO", "CÚBICO")
        words = re.findall(r"[A-Z]{4,15}", normalized)
        ranked = [
            (SequenceMatcher(None, word, product).ratio(), product)
            for word in words for product in products
        ]
        if ranked:
            score, product = max(ranked)
            if score >= 0.80:
                return product.replace("TERCA", "TERÇA").replace("CUBICO", "CÚBICO")
    return None


def decide_fields(
    readings: list[VisionReading],
    crop_paths: dict[str, str] | None = None,
) -> dict[str, FieldDecision]:
    """Resolve each field independently and never trust an isolated number.

    A field is automatically confirmed only when two distinct reading passes
    agree on the same value and both saw that field's printed label. Conflicts
    and single-engine guesses remain pending for the reviewer.
    """
    crop_paths = crop_paths or {}
    all_candidates = [
        candidate
        for reading in readings
        for candidate in _draft_candidates(reading)
    ]
    decisions: dict[str, FieldDecision] = {}
    for field_name in READ_FIELDS:
        candidates = [
            candidate for candidate in all_candidates
            if candidate.field_name == field_name
        ]
        decision = FieldDecision(
            field_name=field_name,
            label=FIELD_LABELS[field_name],
            crop_path=crop_paths.get(field_name, ""),
            candidates=candidates,
        )
        grouped: dict[str, list[FieldCandidate]] = {}
        for candidate in candidates:
            grouped.setdefault(candidate.normalized_value, []).append(candidate)
        # A number may participate in consensus only when at least one source
        # proves which printed field it came from (label text or field crop).
        grouped = {
            value: group for value, group in grouped.items()
            if any(candidate.explicit_label for candidate in group)
        }
        ranked = sorted(
            grouped.values(),
            key=lambda group: (
                len({candidate.engine for candidate in group}),
                sum(candidate.confidence for candidate in group),
            ),
            reverse=True,
        )
        if ranked:
            winner = ranked[0]
            support = len({candidate.engine for candidate in winner})
            competing_support = (
                len({candidate.engine for candidate in ranked[1]})
                if len(ranked) > 1 else 0
            )
            decision.value = winner[0].value
            decision.confidence = round(
                sum(candidate.confidence for candidate in winner) / len(winner), 3
            )
            if support >= 2 and support > competing_support:
                decision.status = "CONFIRMADO_AUTOMATICAMENTE"
                decision.reason = (
                    f"{support} leituras independentes concordaram com o valor."
                )
            elif support == 1:
                strongest = max(candidate.confidence for candidate in winner)
                if (
                    field_name in {"product", "section", "length", "unit_volume"}
                    and strongest >= 0.84
                    and any(candidate.explicit_label for candidate in winner)
                ):
                    decision.status = "CONFIRMADO_AUTOMATICAMENTE"
                    decision.reason = (
                        "Leitura de alta confiança vinculada ao nome impresso do campo."
                    )
                else:
                    decision.reason = "Somente uma leitura comprovou este campo."
            else:
                decision.reason = "Leituras conflitantes para este campo."
        elif candidates:
            decision.reason = (
                "O valor apareceu sem o nome do campo legível; não foi preenchido automaticamente."
            )
        decisions[field_name] = decision
    return decisions


def _save_evidence_crops(image_path: Path, output_dir: Path) -> tuple[str, dict[str, str]]:
    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()[:12]
    target = output_dir / f"{image_path.stem}_{digest}"
    target.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as source:
        label = _orange_label_crop(source) or source.convert("RGB")
        prepared = _prepare_paddle_label(label)
    label_path = target / "etiqueta.png"
    prepared.save(label_path, format="PNG", optimize=True)
    crop_paths: dict[str, str] = {}
    for field_name, (top, bottom, left, right) in FIELD_BANDS.items():
        box = (
            round(prepared.width * left), round(prepared.height * top),
            round(prepared.width * right), round(prepared.height * bottom),
        )
        crop_path = target / f"campo_{field_name}.png"
        prepared.crop(box).save(crop_path, format="PNG", optimize=True)
        crop_paths[field_name] = str(crop_path)
    return str(label_path), crop_paths


def _read_isolated_fields(
    crop_paths: dict[str, str],
    field_names: set[str] | None = None,
) -> list[VisionReading]:
    """Read field strips as a third pass, independent of full-label layout."""
    if not paddle_available():
        return []
    ordered_fields = [
        field_name
        for field_name in ("work", "product", "section", "length", "unit_volume", "piece")
        if crop_paths.get(field_name)
        and (field_names is None or field_name in field_names)
    ]
    ordered_paths = [Path(crop_paths[field_name]) for field_name in ordered_fields]
    readings = read_paddle_line_texts(ordered_paths, quality="medium")
    return [
        VisionReading(
            engine=f"campo_isolado_{field_name}",
            text=str(text).strip(),
            confidence=float(confidence),
            field_hint=field_name,
        )
        for field_name, (text, confidence) in zip(ordered_fields, readings)
        if str(text).strip() and float(confidence) >= 0.30
    ]


def analyze_image(image_path: Path, output_dir: Path) -> VisionAnalysis:
    """Create an auditable local analysis without touching the workbook."""
    label_path, crop_paths = _save_evidence_crops(image_path, output_dir)
    if paddle_available():
        # A fast neural pass and the independent Windows OCR read the same
        # rectified label.  The accurate neural recognizer is then reserved,
        # in shared batches, only for fields on which these passes do not
        # agree.  This preserves consensus without taking hours per fortnight.
        small_text, small_confidence = read_paddle_text(
            Path(label_path), quality="small"
        )
        try:
            windows_text = _read_variant(Path(label_path))
        except Exception:
            windows_text = ""
        readings = [
            VisionReading(
                engine="ppocr_v6_small",
                text=small_text,
                confidence=float(small_confidence),
            ),
            VisionReading(
                engine="windows_ocr",
                text=windows_text,
                confidence=0.70 if windows_text else 0.0,
            ),
        ]
    else:
        primary = read_image_text(image_path)
        targeted = read_image_text_targeted(image_path)
        readings = [
            VisionReading(
                engine="leitura_principal",
                text=primary.text,
                confidence=min(0.99, max(0.0, primary.score / 220)),
            ),
            VisionReading(
                engine="leitura_direcionada",
                text=targeted.text,
                confidence=min(0.99, max(0.0, targeted.score / 220)),
            ),
        ]
    decisions = decide_fields(readings, crop_paths)
    product = decisions["product"].value or ""
    length = decisions["length"].value or ""
    parsed_length = None
    if length:
        try:
            parsed_length = float(str(length).replace(".", "").replace(",", "."))
        except ValueError:
            pass
    product_type = normalize_type("", str(product), parsed_length) if product else ""
    return VisionAnalysis(
        source_path=str(image_path),
        label_crop_path=label_path,
        fields=decisions,
        readings=readings,
        product_type=product_type,
    )


def enrich_isolated_fields_batch(
    analyses: list[VisionAnalysis],
    batch_size: int = 64,
) -> None:
    """Re-read only unresolved field strips in efficient shared batches."""
    if not analyses or not paddle_available():
        return
    jobs: list[tuple[VisionAnalysis, str, Path]] = []
    for analysis in analyses:
        for field_name, decision in analysis.fields.items():
            if (
                decision.status != "CONFIRMADO_AUTOMATICAMENTE"
                and decision.crop_path
                and Path(decision.crop_path).exists()
                and not any(
                    reading.field_hint == field_name
                    for reading in analysis.readings
                )
            ):
                jobs.append((analysis, field_name, Path(decision.crop_path)))
    for offset in range(0, len(jobs), max(1, batch_size)):
        batch = jobs[offset:offset + max(1, batch_size)]
        recognized = read_paddle_line_texts(
            [path for _, _, path in batch], quality="small"
        )
        for (analysis, field_name, _), (text, confidence) in zip(batch, recognized):
            # Keep an empty/low-confidence attempt in the audit too, so a
            # reopened review does not rerun the same expensive crop forever.
            analysis.readings.append(VisionReading(
                engine=f"campo_isolado_{field_name}",
                text=str(text).strip() if float(confidence) >= 0.30 else "",
                confidence=float(confidence),
                field_hint=field_name,
            ))
    for analysis in analyses:
        crop_paths = {
            name: decision.crop_path
            for name, decision in analysis.fields.items()
        }
        analysis.fields = decide_fields(analysis.readings, crop_paths)
        product = analysis.fields["product"].value or ""
        length = analysis.fields["length"].value or ""
        parsed_length = None
        if length:
            try:
                parsed_length = float(str(length).replace(".", "").replace(",", "."))
            except ValueError:
                pass
        analysis.product_type = (
            normalize_type("", str(product), parsed_length) if product else ""
        )


def _evidence_group(source_path: str) -> str:
    stem = Path(source_path).stem
    match = re.match(r"(.+?)_[0-9a-f]{12}_foto_\d+$", stem, re.IGNORECASE)
    return match.group(1) if match else stem


def apply_group_context(analyses: list[VisionAnalysis]) -> None:
    """Use safe message-level context without copying piece measurements."""
    grouped: dict[str, list[VisionAnalysis]] = {}
    for analysis in analyses:
        grouped.setdefault(_evidence_group(analysis.source_path), []).append(analysis)
    for group in grouped.values():
        confirmed_works = [
            str(analysis.fields["work"].value)
            for analysis in group
            if analysis.fields["work"].status == "CONFIRMADO_AUTOMATICAMENTE"
            and analysis.fields["work"].value
        ]
        unique_works = set(confirmed_works)
        if len(confirmed_works) >= 2 and len(unique_works) == 1:
            agreed_work = confirmed_works[0]
            for analysis in group:
                decision = analysis.fields["work"]
                if decision.status != "CONFIRMADO_AUTOMATICAMENTE":
                    decision.value = agreed_work
                    decision.confidence = 0.90
                    decision.status = "CONFIRMADO_AUTOMATICAMENTE"
                    decision.reason = (
                        f"{len(confirmed_works)} fotos do mesmo álbum concordaram com a obra."
                    )
        for analysis in group:
            product = analysis.fields["product"]
            piece = analysis.fields["piece"]
            if (
                product.status != "CONFIRMADO_AUTOMATICAMENTE"
                and piece.status == "CONFIRMADO_AUTOMATICAMENTE"
                and piece.value
            ):
                inferred = _product_from_piece(str(piece.value))
                if inferred:
                    product.value = inferred
                    product.confidence = piece.confidence
                    product.status = "CONFIRMADO_AUTOMATICAMENTE"
                    product.reason = (
                        f"Produto determinado pela família comprovada da peça {piece.value}."
                    )
            product_value = analysis.fields["product"].value or ""
            length_value = analysis.fields["length"].value or ""
            parsed_length = None
            if length_value:
                try:
                    parsed_length = float(
                        str(length_value).replace(".", "").replace(",", ".")
                    )
                except ValueError:
                    pass
            analysis.product_type = (
                normalize_type("", str(product_value), parsed_length)
                if product_value else ""
            )


def evaluate_against_reference(
    analysis: VisionAnalysis,
    reference: dict[str, object],
) -> dict[str, object]:
    """Measure field decisions without changing either analysis or review."""
    fields: dict[str, dict[str, object]] = {}
    automatic = 0
    correct = 0
    divergent = 0
    pending = 0
    for field_name in READ_FIELDS:
        decision = analysis.fields[field_name]
        expected = reference.get(field_name)
        expected_key = _normalized_value(field_name, expected)
        actual_key = _normalized_value(field_name, decision.value)
        if decision.status != "CONFIRMADO_AUTOMATICAMENTE":
            outcome = "PENDENTE"
            pending += 1
        else:
            automatic += 1
            if expected_key and actual_key == expected_key:
                outcome = "CORRETO"
                correct += 1
            else:
                outcome = "DIVERGENTE"
                divergent += 1
        fields[field_name] = {
            "esperado": expected,
            "obtido": decision.value,
            "resultado": outcome,
        }
    return {
        "campos": fields,
        "confirmados_automaticamente": automatic,
        "corretos": correct,
        "divergentes": divergent,
        "pendentes": pending,
        "precisao_automatica_percentual": (
            round(correct / automatic * 100, 1) if automatic else None
        ),
    }
