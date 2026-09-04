from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher


def _plain(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value or "")
    return "".join(
        character for character in decomposed
        if not unicodedata.combining(character)
    )


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip(" :-\t")


_PIECE_PATTERN = re.compile(
    r"[A-Z]{1,6}[-_]?\d{1,4}[A-Z]?(?:[-_][A-Z0-9]+)*",
    re.IGNORECASE,
)


def _valid_piece(value: str) -> bool:
    return bool(_PIECE_PATTERN.fullmatch(_plain(value).upper().replace(" ", "")))


def _product_from_piece(piece: str) -> str:
    """Infer the catalog product only from unambiguous code families."""
    match = re.match(r"([A-Z]+)", _plain(piece).upper().replace(" ", ""))
    prefix = match.group(1) if match else ""
    if prefix in {"PH", "PP"}:
        return "PILAR"
    if prefix == "PM":
        return "PAINEL"
    if prefix in {"VPT", "VPR", "VRT", "VCR", "VOL", "VL", "VR", "VP"}:
        return "VIGA"
    if prefix == "MA":
        return "MURO"
    if prefix == "BL":
        return "BLOCO"
    return ""


def _repair_ocr_labels(text: str) -> str:
    """Repair frequent Windows-OCR distortions of printed field labels."""
    repaired = _plain(text)
    repaired = re.sub(r"[‐‑‒–—−�]", "-", repaired)
    repaired = re.sub(
        r"\bS\s*:\s*(?=\d{1,3}\s*[Xx]\s*\d{1,3}\b)",
        "secao: ",
        repaired,
        flags=re.IGNORECASE,
    )
    replacements = (
        (r"\bsec(?:a|c|o|0|ao|ac)[o0a]?\b", "secao"),
        (r"\bcompr\W{0,3}ment\w*\b", "comprimento"),
        (r"\bcomovimento\w*\b", "comprimento"),
        (r"\bcom(?:p|o)?r?i?m(?:e|e?n|e?nt|ento)[a-z]*\b", "comprimento"),
        (r"\b(?:vo[l1i]|voj|voi|vo1|vt|vl)\b", "vol"),
        (r"\bpelar\b", "PILAR"),
        (r"\bpeca\b", "peca"),
        (r"\bpro(?:duto|coto|dutos?)\b", "produto"),
        (r"\bobra\b", "obra"),
    )
    for pattern, value in replacements:
        repaired = re.sub(pattern, value, repaired, flags=re.IGNORECASE)
    def repair_decimal(match: re.Match[str]) -> str:
        whole = match.group(1).upper().replace("I", "1").replace("L", "1").replace("O", "0")
        return f"{whole},{match.group(2)}"
    repaired = re.sub(r"\b([0-9ILO]{1,2})\s*,\s*(\d{3})\b", repair_decimal, repaired)
    return repaired


def _field(text: str, label: str, next_labels: tuple[str, ...]) -> str:
    # PaddleOCR preserves visual line order. Prefer a value printed on the
    # same line as the label, or on the immediately following line when the
    # label ends with a colon (notably `Peça:` / `PH-14`).
    lines = [_clean(line) for line in _plain(text).splitlines() if _clean(line)]
    for index, line in enumerate(lines):
        match = re.match(rf"(?i)^\s*{re.escape(label)}\s*[:.]?\s*(.*)$", line)
        if not match:
            continue
        value = _clean(match.group(1))
        if value:
            return value
        if index + 1 < len(lines):
            following = lines[index + 1]
            if not any(re.match(rf"(?i)^\s*{re.escape(item)}\b", following) for item in next_labels):
                return _clean(following)
    stop = "|".join(re.escape(item) for item in next_labels)
    boundary = rf"(?=\s*\b(?:{stop})\b\s*[:.]?|$)" if stop else r"(?=$)"
    match = re.search(
        rf"(?is)\b{re.escape(label)}\s*[:.]?\s*(.+?){boundary}",
        _plain(text),
    )
    return _clean(match.group(1)) if match else ""


def _decimal(value: str) -> float | None:
    match = re.search(r"\d+(?:[.,]\d+)?", value or "")
    if not match:
        return None
    try:
        return float(match.group(0).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _decimal_measurement(value: str) -> float | None:
    """Read measurements when OCR changes the Brazilian comma into a dot."""
    match = re.search(r"\d+(?:[.,]\d+)?", value or "")
    if not match:
        return None
    token = match.group(0)
    try:
        if "," in token:
            return float(token.replace(".", "").replace(",", "."))
        return float(token)
    except ValueError:
        return None


def _measurement(value: str) -> str:
    return _clean(re.sub(r"(?i)^\s*[.]?\s*\([^)]*\)\s*[:.]?\s*", "", value or ""))


def _majority_explicit_length(text: str) -> str:
    """Choose a repeated explicit length over one isolated OCR distortion."""
    values = re.findall(
        r"(?i)\bcomprimento\s*(?:\([^)]*\))?\s*[:.]?\s*(\d{1,2}[.,]\d{3})",
        _plain(text),
    )
    if len(values) < 2:
        return ""
    canonical = [value.replace(".", ",") for value in values]
    agreed, support = Counter(canonical).most_common(1)[0]
    if support >= 2 and support / len(canonical) >= 0.60:
        return agreed
    return ""


def _normalize_section(value: str) -> str:
    """Normalize the common OCR confusion E=IO -> E=10, never inventing other digits."""
    cleaned = _clean(value).upper().replace(" ", "")
    cleaned = re.sub(r"^E[-:]", "E=", cleaned)
    cleaned = re.sub(r"^E=IO(?:([.,]\d+))?$", r"E=10\1", cleaned)
    # Structural sections on these labels are expressed in centimetres with
    # at least two digits per side.  A lone final digit is a common OCR loss
    # at the right border (40X6 -> 40X60), never a valid workbook dimension.
    truncated = re.fullmatch(r"(\d{2,3})X(\d)", cleaned)
    if truncated:
        cleaned = f"{truncated.group(1)}X{truncated.group(2)}0"
    return cleaned


def _recover_volume_tail_from_weight(text: str, excluded: set[float]) -> float | None:
    """Recover a volume whose leading digit was obscured but decimals survived.

    The printed label contains both weight and unit volume.  Precast concrete
    densities in this dataset sit safely between 2,200 and 2,700 kg/m³.  We
    accept a recovered leading digit only when exactly one digit produces a
    physically plausible density; otherwise the field remains pending.
    """
    plain = _plain(text)
    weight_match = re.search(
        r"(?is)\bpeso\b.{0,20}?(\d{3,6}[.,]\d{2})",
        plain,
    )
    volume_match = re.search(
        r"(?is)\bvol(?:ume)?\b.{0,18}?(?:[<>()'\"=:.,\s]*)(\d{3})\b",
        plain,
    )
    if not weight_match or not volume_match:
        return None
    weight = _decimal_measurement(weight_match.group(1))
    if weight is None:
        return None
    fraction = int(volume_match.group(1)) / 1000
    candidates = []
    for leading in range(1, 10):
        value = leading + fraction
        density = weight / value
        if (
            2200 <= density <= 2700
            and all(abs(value - blocked) > 0.0001 for blocked in excluded)
        ):
            candidates.append(value)
    return candidates[0] if len(candidates) == 1 else None


def _explicit_label_volume(text: str, excluded: set[float] | None = None) -> float | None:
    """Read only the number immediately following the printed Vol./Volume label."""
    match = re.search(
        r"(?is)\b(?:vol(?:ume)?)\s*\.?\s*(?:\([^)]*\))?\s*[:.]?\s*(\d+[.,]\d+)",
        _plain(text),
    )
    if not match:
        match = re.search(r"(?is)\b(?:m3|mm)\s*[:.]?\s*(\d+[.,]\d+)", _plain(text))
    excluded = excluded or set()
    if match:
        value = _decimal_measurement(match.group(1))
        if value is not None and all(abs(value - blocked) > 0.0001 for blocked in excluded):
            return value
    # OCR frequently moves the value away from `Vol. (m3):`.  A volume on
    # these labels is a three-decimal number up to 10; weights are much larger
    # and are therefore excluded.
    if re.search(r"\bvol(?:ume)?\b|\bm3\b", _plain(text), re.IGNORECASE):
        candidates = [
            _decimal_measurement(token)
            for token in re.findall(r"\b\d{1,2}[.,]\d{3}\b", _plain(text))
        ]
        candidates = [
            value for value in candidates
            if value is not None and 0 < value <= 10
            and all(abs(value - blocked) > 0.0001 for blocked in excluded)
        ]
        if candidates:
            return candidates[-1]
    return None


def _explicit_known_work(text: str) -> str:
    """Recover only clearly printed, known work names when OCR loses `Obra:`."""
    normalized = _plain(text).upper()
    # In the validated AWL sample, sigla 2301 occurred 66 times and all
    # readable instances identify this same work. This also recovers labels
    # where glare erased the word VENTISOL but left the sigla intact.
    if re.search(r"\b2301\b", normalized):
        return "VENTISOL - GALPAO VERTICAL 282"
    if re.search(r"\b0?104\b", normalized) and "ALUMIN" in normalized:
        return "AMPLIACAO ALUMINIO SJ"
    if re.search(r"\b0?226\b", normalized) and "MKM" in normalized:
        return "MKM GALPAO COMERCIAL"
    for pattern, value in (
        (r"VENTISOL\s*-\s*GALPAO VERTICAL\s*282", "VENTISOL - GALPAO VERTICAL 282"),
        (r"AMPL(?:IACAO|IACAO|I)?\s+ALUMINIO\s*S[J1]", "AMPLIACAO ALUMINIO SJ"),
        (r"VENTISOL\s*-\s*GUARDA DO CUBATAO", "VENTISOL - GUARDA DO CUBATAO"),
        (r"CEJEN\s*-\s*PORTO IMBITUBA", "CEJEN - PORTO IMBITUBA"),
        (r"MKM\s+GALPAO COMERCIAL", "MKM GALPAO COMERCIAL"),
        (r"UNITERMI\s*-\s*AMPLIACAO\s+FABRIL", "UNITERMI - AMPLIACAO FABRIL"),
    ):
        if re.search(pattern, normalized):
            return value
    return ""


def _fuzzy_known_work(text: str) -> str:
    """Match a damaged work line against the small, known work catalogue."""
    normalized_lines = [
        re.sub(r"[^A-Z0-9]", "", _plain(line).upper())
        for line in text.splitlines()
        if len(_clean(line)) >= 8
    ]
    catalog = (
        "VENTISOL - GALPAO VERTICAL 282",
        "AMPLIACAO ALUMINIO SJ",
        "VENTISOL - GUARDA DO CUBATAO",
        "CEJEN - PORTO IMBITUBA",
        "MKM GALPAO COMERCIAL",
        "UNITERMI - AMPLIACAO FABRIL",
    )
    best_value = ""
    best_score = 0.0
    for value in catalog:
        target = re.sub(r"[^A-Z0-9]", "", _plain(value).upper())
        for line in normalized_lines:
            score = SequenceMatcher(None, line, target).ratio()
            if score > best_score:
                best_value, best_score = value, score
    return best_value if best_score >= 0.72 else ""


def _explicit_product(text: str) -> str:
    normalized = _plain(text).upper()
    # The workbook catalog uses the base product names.  Descriptors printed
    # after the hyphen (MACIÇO, RETANGULAR, VASO, etc.) must not become a new
    # product value or the spreadsheet lookup will fail.
    for pattern, value in (
        (r"(?:(?:L\s*)?APOIO\s+)?DE\s+LAJE", "VIGA"),
        (r"PAINEL(?:\s*-\s*(?:MACICO|CONTENCAO))?", "PAINEL"),
        (r"PILAR(?:\s*-\s*RETANGULAR)?", "PILAR"),
        (r"VIGA(?:\s*-\s*(?:RETANGULAR|VASO))?", "VIGA"),
        (r"LAJE(?:\s*-\s*MACICA|\s+ALVEOLAR)", "LAJE ALVEOLAR"),
    ):
        if re.search(pattern, normalized):
            return value
    return ""


def _single_explicit_piece(text: str) -> str:
    normalized = _plain(text).upper()
    candidates = {
        re.sub(r"\s+", "", item)
        for item in re.findall(
            r"\b(?:PL|PM|VPT|VPR|VRT|VCR|VOL|VL|VR|VP|PP|PH|PA|MA|BL|EP)"
            r"[-_]?\s*\d{1,4}[A-Z]?(?:[-_][A-Z0-9]+)?\b",
            normalized,
        )
    }
    if not candidates:
        # Repair I/O/L only inside the numeric suffix of a known piece code.
        noisy = re.findall(
            r"\b(?:PL|PM|VPT|VPR|VRT|VCR|VOL|VL|VR|VP|PP|PH|PA|MA|BL|EP)"
            r"[-_]\s*[0-9IOL]{1,4}(?:[-_][A-Z0-9]+)?\b",
            normalized,
        )
        for item in noisy:
            prefix, suffix = re.split(r"[-_]", re.sub(r"\s+", "", item), maxsplit=1)
            suffix = suffix.replace("I", "1").replace("L", "1").replace("O", "0")
            if re.match(r"^\d", suffix):
                candidates.add(f"{prefix}-{suffix}")
    if len(candidates) != 1:
        return ""
    value = next(iter(candidates))
    # PH-## and PP-## are both valid, distinct piece-code families. Never
    # convert one prefix into the other.
    return value


def _single_explicit_section(text: str) -> str:
    normalized = _plain(text).upper()
    if re.search(r"\bVARIAVEL\b", normalized):
        return "VARIAVEL"
    candidates = {
        re.sub(r"\s+", "", item)
        for item in re.findall(r"\b(?:E\s*[-=:]\s*[0-9IOL]+(?:[.,]\d+)?|\d{2,3}\s*X\s*\d{2,3})\b", normalized)
    }
    if len(candidates) == 1:
        return next(iter(candidates))
    # On small labels Paddle can read the printed zero as C/O and X as K.
    # Repair only a complete, plausible two-dimensional token.
    noisy = re.findall(r"\b[0-9OCS]{2,3}\s*[XK*]\s*[0-9OCS]{1,3}\b", normalized)
    repaired: set[str] = set()
    for value in noisy:
        value = (
            re.sub(r"\s+", "", value)
            .replace("O", "0").replace("C", "0")
            .replace("S", "5").replace("K", "X").replace("*", "X")
        )
        left, right = value.split("X", 1)
        if 10 <= int(left) <= 1000 and 10 <= int(right) <= 1000:
            repaired.add(value)
    return next(iter(repaired)) if len(repaired) == 1 else ""


def _unlabelled_measurements(text: str) -> tuple[str, float | None]:
    """Recover length/volume when OCR read values but dropped field labels.

    A pair is safe because the label uses a length up to 30 m and a much
    smaller unit volume, both with three decimals; the two-decimal weight and
    integer QR identifier are excluded.  A single value remains ambiguous.
    """
    candidates: list[tuple[str, float]] = []
    for token in re.findall(r"\b\d{1,2}[.,]\d{3}\b", _plain(text)):
        value = _decimal_measurement(token)
        if value is not None and 0 < value <= 30:
            candidates.append((token, value))
    unique: dict[float, str] = {}
    for token, value in candidates:
        unique.setdefault(value, token)
    if len(unique) == 1:
        value, token = next(iter(unique.items()))
        if value > 10:
            return token, None
        if re.search(r"\bvol(?:ume)?\b", _repair_ocr_labels(text), re.IGNORECASE):
            return "", value
        return "", None
    if len(unique) < 2:
        return "", None
    ordered = sorted(unique.items())
    volume_value, _ = ordered[0]
    length_value, length_token = ordered[-1]
    if length_value <= volume_value:
        return "", None
    return length_token, volume_value


def normalize_type(work: str, product: str, length: float | None, group: str = "") -> str:
    work_key = _plain(work).upper()
    product_key = _plain(product).upper()
    group_key = _plain(group).upper()
    if "CEJEN" in work_key and "PORTO IMBITUBA" in work_key:
        return "METRO CÚBICO"
    if "VIGA" in product_key and "TERCA T" in group_key:
        return "VIGA TERÇA"
    for source, target in (
        ("PAINEL", "PAINEL"),
        ("PILAR", "PILAR"),
        ("BLOCO", "BLOCO"),
        ("MURO", "MURO"),
        ("ESCADA", "ESCADA"),
        ("LAJE", "LAJE ALVEOLAR"),
    ):
        if source in product_key:
            return target
    if "VIGA" in product_key and length is not None:
        if length <= 6:
            return "VIGA ATÉ 6m"
        if length <= 8.9:
            return "VIGA 6,1 ATÉ 8,9m"
        if length <= 10:
            return "VIGA 9m ATÉ 10m"
        if length <= 15.55:
            return "VIGA 10,1m ATÉ 15,55m"
        return "VIGA 15,56m ATÉ 25m"
    return ""


@dataclass
class LabelDraft:
    message_id: str
    message_date: str
    source_path: str
    work: str = ""
    product: str = ""
    type_name: str = ""
    piece: str = ""
    section: str = ""
    length: str = ""
    dimensions: str = ""
    unit_volume: float | None = None
    quantity: int | float = 1
    cargo_type: str = "PEÇAS ESTOQUE"
    status: str = "PENDENTE"
    warnings: list[str] = field(default_factory=list)
    ocr_text: str = ""


def parse_label_text(
    text: str,
    *,
    message_id: str = "",
    message_date: str = "",
    source_path: str = "",
    group: str = "",
) -> LabelDraft:
    text = _repair_ocr_labels(text)
    labels = (
        "obra", "sigla", "produto", "secao", "comprimento",
        "peso", "peca", "vol", "volume",
    )
    work = _field(text, "obra", labels[1:])
    product = _field(text, "produto", ("secao", "comprimento", "peso", "peca", "vol", "volume"))
    section = _normalize_section(_field(text, "secao", ("comprimento", "peso", "peca", "vol", "volume")))
    length_text = _measurement(
        _field(text, "comprimento", ("peso", "peca", "vol", "volume"))
    )
    piece = _field(text, "peca", ("vol", "volume"))
    # OCR may miss the next field label and accidentally consume the rest of
    # the page. Never present that long passage as a confirmed field value.
    if len(work) > 80:
        work = ""
    if len(product) > 50:
        product = ""
    if len(section) > 24:
        section = ""
        section = _normalize_section(_single_explicit_section(text))
    if len(length_text) > 20:
        length_text = ""
    if len(piece) > 24:
        piece = ""
    known_work = _explicit_known_work(text)
    if known_work:
        work = known_work
    else:
        fuzzy_work = _fuzzy_known_work(text)
        if fuzzy_work:
            work = fuzzy_work
    known_product = _explicit_product(text)
    if known_product:
        product = known_product
    else:
        # Canonicalize a field captured with a descriptor, but only when the
        # base name is explicit in the printed product field.
        product_key = _plain(product).upper()
        for marker, canonical in (
            ("PAINEL", "PAINEL"), ("PILAR", "PILAR"), ("VIGA", "VIGA"),
            ("LAJE ALVEOLAR", "LAJE ALVEOLAR"),
            ("BLOCO", "BLOCO"), ("MURO", "MURO"), ("ESCADA", "ESCADA"),
        ):
            if marker in product_key:
                product = canonical
                break
    if _plain(product).upper() not in {
        "PAINEL", "PILAR", "VIGA", "LAJE ALVEOLAR", "BLOCO", "MURO", "ESCADA",
    }:
        product = ""
    if not section:
        section = _normalize_section(_single_explicit_section(text))
    if not piece:
        piece = _single_explicit_piece(text)
    inferred_length, inferred_volume = _unlabelled_measurements(text)
    majority_length = _majority_explicit_length(text)
    if majority_length:
        length_text = majority_length
    # If the label was read but its value was moved by OCR, recover only a
    # plausible piece length (1–30 m, three decimal places).  Weight/QR values
    # are intentionally excluded.
    if not length_text and re.search(r"\bcomprimento\b", text, re.IGNORECASE):
        measurements = [
            token for token in re.findall(r"\b\d{1,2}[.,]\d{3}\b", text)
            if 0 < (_decimal_measurement(token) or 0) <= 30
        ]
        if measurements:
            length_text = measurements[0]
    if not length_text and inferred_length:
        length_text = inferred_length
    if section and not re.fullmatch(r"VARIAVEL|E=\d{1,3}(?:[.,]\d+)?|\d{1,3}(?:[.,]\d+)?X\d{1,3}(?:[.,]\d+)?(?:/\d{1,3}(?:[.,]\d+)?)?", section):
        section = ""
        section = _normalize_section(_single_explicit_section(text))
    if section.startswith("E=") and not (0 < (_decimal_measurement(section[2:]) or 0) <= 50):
        section = ""
    if "X" in section:
        numeric_parts = [
            _decimal_measurement(part)
            for part in re.split(r"X|/", section)
        ]
        if any(value is None or value < 10 or value > 1000 for value in numeric_parts):
            section = ""
    if length_text and not re.fullmatch(r"\d+[.,]\d{1,3}", length_text):
        length_text = ""
    if length_text and not (0 < (_decimal_measurement(length_text) or 0) <= 30):
        length_text = ""
    if not length_text and re.search(r"\bcomprimento\b", text, re.IGNORECASE):
        measurements = [
            token for token in re.findall(r"\b\d{1,2}[.,]\d{3}\b", text)
            if 0 < (_decimal_measurement(token) or 0) <= 30
        ]
        if measurements:
            length_text = measurements[0]
    piece_key_initial = _plain(piece).upper().replace(" ", "")
    if not _valid_piece(piece_key_initial):
        piece = _single_explicit_piece(text)
        piece_key_initial = _plain(piece).upper().replace(" ", "")
    if not _valid_piece(piece_key_initial):
        piece_before_label = re.search(
            r"(?i)\b([A-Z]{1,6}[-_]?\d{1,4}[A-Z]?(?:[-_][A-Z0-9]+)*)\s+peca\s*[:.]?",
            _plain(text),
        )
        if piece_before_label:
            piece = _clean(piece_before_label.group(1)).upper()
    if (
        product == "VIGA"
        and re.search(r"(?i)(?:APOIO\s+)?DE\s+LAJE", _plain(text))
        and re.fullmatch(r"VOL[-_]?\d{1,4}", _plain(piece).upper().replace(" ", ""))
    ):
        piece = re.sub(r"(?i)^VOL", "VL", piece)
    if not product and piece:
        product = _product_from_piece(piece)
    excluded_measurements = {
        value for value in (_decimal_measurement(length_text),) if value is not None
    }
    explicit_volume = _explicit_label_volume(text, excluded_measurements)
    if explicit_volume is None:
        explicit_volume = _recover_volume_tail_from_weight(text, excluded_measurements)
    length_value = _decimal_measurement(length_text)
    if (
        explicit_volume is None
        and inferred_volume is not None
        and (length_value is None or abs(inferred_volume - length_value) > 0.0001)
    ):
        explicit_volume = inferred_volume
    volume_over_limit = explicit_volume is not None and explicit_volume > 10
    if volume_over_limit:
        explicit_volume = None
    volume_text = str(explicit_volume).replace(".", ",") if explicit_volume is not None else ""
    length = _decimal_measurement(length_text)
    unit_volume = explicit_volume
    if (
        length is not None
        and unit_volume is not None
        and abs(length - unit_volume) < 0.0001
    ):
        # One printed token was assigned to two different fields. Keep the
        # explicit volume and request the missing length instead of silently
        # approving duplicated data.
        length_text = ""
        length = None
    type_name = normalize_type(work, product, length, group)
    dimensions = " ".join(item for item in (_clean(section), _clean(length_text)) if item)

    warnings: list[str] = []
    if volume_over_limit:
        warnings.append("Confirmar volume unitário: valor lido parece ser peso/QR, não volume")
    for label, value in (
        ("obra", work),
        ("produto", product),
        ("peça", piece),
        ("seção", section),
        ("comprimento", length_text),
        ("volume unitário", unit_volume),
        ("tipo normalizado", type_name),
        ("data da mensagem", message_date),
    ):
        if value in ("", None):
            warnings.append(f"Confirmar {label}")
    piece_key = _plain(piece).upper().replace(" ", "")
    if piece and not _valid_piece(piece_key):
        warnings.append("Confirmar peça: formato não reconhecido")
    section_key = _plain(section).upper().replace(" ", "")
    if section and not (
        re.fullmatch(r"E=\d{1,3}(?:[.,]\d+)?", section_key)
        or section_key == "VARIAVEL"
        or re.fullmatch(r"\d{1,3}(?:[.,]\d+)?X\d{1,3}(?:[.,]\d+)?(?:/\d{1,3}(?:[.,]\d+)?)?", section_key)
    ):
        warnings.append("Confirmar seção: formato não reconhecido")

    return LabelDraft(
        message_id=message_id,
        message_date=message_date,
        source_path=source_path,
        work=work,
        product=type_name or product,
        type_name=type_name,
        piece=piece,
        section=section,
        length=length_text,
        dimensions=dimensions,
        unit_volume=unit_volume,
        status="PRONTO PARA REVISÃO" if not warnings else "CONFIRMAR",
        warnings=warnings,
        ocr_text=text,
    )


def _romaneio_product(text: str, row_count: int) -> str:
    normalized = _plain(text).upper()
    candidates = (
        ("PAINEL", "PAINEL"),
        ("VIGA", "VIGA"),
        ("PILAR", "PILAR"),
        ("LAJE", "LAJE"),
        ("BLOCO", "BLOCO"),
        ("MURO", "MURO"),
        ("ESCADA", "ESCADA"),
    )
    for marker, product in candidates:
        if normalized.count(marker) >= row_count:
            return product
    return ""


def parse_romaneio_text(
    text: str,
    *,
    message_id: str = "",
    message_date: str = "",
    source_path: str = "",
    group: str = "",
) -> list[LabelDraft]:
    """Split a flattened OCR reading of a cargo manifest into piece rows.

    OCR normally returns the table column by column.  The parser therefore only
    accepts explicit runs of piece, section, length and volume values and marks
    every mismatch for human confirmation instead of inventing a value.
    """
    plain = _plain(text)
    upper = plain.upper()
    total_index = upper.find("TOTAL")
    volume_index = upper.find("VOLUME", total_index + 1)
    weight_index = upper.find("PESO", volume_index + 1)
    if total_index < 0 or volume_index < 0:
        return []

    piece_area = upper[:total_index]
    piece_candidates = re.findall(r"\b[A-Z]{1,6}-?\s*\d+[A-Z]?\b", piece_area)
    excluded_prefixes = ("CEP", "CPF")
    pieces = [
        re.sub(r"\s+", "", item)
        for item in piece_candidates
        if not item.startswith(excluded_prefixes)
        and not re.fullmatch(r"E\s*=?.*", item)
    ]
    # Piece codes are located at the end of the first table-column block.
    prefab_index = upper.rfind("PREFABRICA", 0, total_index)
    if prefab_index >= 0:
        tail = upper[prefab_index + len("PREFABRICA"):total_index]
        tail_pieces = re.findall(
            r"\b[A-Z]{2,6}(?:-\s*)?(?:\d+[A-Z]?|[IO][A-ZIO0-9]*)(?:\s+\d+)?\b",
            tail,
        )
        if tail_pieces:
            pieces = [re.sub(r"\s+", "", item) for item in tail_pieces]
    if not pieces:
        return []

    row_count = len(pieces)
    measurements_area = upper[total_index:volume_index]
    sections = [
        re.sub(r"\s+", "", item)
        for item in re.findall(r"\bE\s*=\s*(?:\d+|IO)(?:[.,]\d+)?", measurements_area)
    ]
    after_sections = measurements_area
    if sections:
        last_section = list(re.finditer(r"\bE\s*=\s*(?:\d+|IO)(?:[.,]\d+)?", measurements_area))[-1]
        after_sections = measurements_area[last_section.end():]
    lengths = re.findall(r"\b\d{1,2}[.,]\d{1,3}\b", after_sections)[:row_count]

    volume_end = weight_index if weight_index > volume_index else len(upper)
    volume_area = upper[volume_index:volume_end]
    volumes = re.findall(r"\b(?:\d{1,2}[.,]\d{3}|\d{4})\b", volume_area)[:row_count]
    product = _romaneio_product(upper[volume_index:], row_count)

    work = ""
    header_match = re.search(r"ROMANEIO DE CARGAS\s*[|:\-\u2022]?\s*(.*?)\s+OBRA\b", upper)
    if header_match:
        work = _clean(re.sub(r"^\d+(?:\s*[|]\s*|\s+)", "", header_match.group(1)))

    drafts: list[LabelDraft] = []
    for index, piece in enumerate(pieces):
        section = _normalize_section(sections[index]) if index < len(sections) else ""
        length_text = lengths[index] if index < len(lengths) else ""
        volume_text = volumes[index] if index < len(volumes) else ""
        length = _decimal_measurement(length_text)
        unit_volume = _decimal_measurement(volume_text)
        type_name = normalize_type(work, product, length, group)
        warnings: list[str] = []
        for label, value in (
            ("obra", work),
            ("produto", product),
            ("seção", section),
            ("comprimento", length_text),
            ("volume unitário", unit_volume),
            ("tipo normalizado", type_name),
            ("data da mensagem", message_date),
        ):
            if value in ("", None):
                warnings.append(f"Confirmar {label}")
        piece_key = piece.replace(" ", "")
        if (
            not re.fullmatch(r"[A-Z]{1,6}-?\d+[A-Z]?", piece_key)
            or re.search(r"I(?=\d)|[IO]{2,}", piece_key)
        ):
            warnings.append(f"Confirmar peça lida no romaneio: {piece}")
        if section and not re.fullmatch(r"E=\d+(?:[.,]\d+)?", section):
            warnings.append(f"Confirmar seção lida no romaneio: {section}")
        if unit_volume is not None and unit_volume > 10:
            warnings.append(f"Confirmar volume lido no romaneio: {volume_text}")
            unit_volume = None
        if not (len(sections) >= row_count and len(lengths) >= row_count and len(volumes) >= row_count):
            warnings.append("Confirmar colunas do romaneio: leitura incompleta")
        drafts.append(LabelDraft(
            message_id=f"{message_id}:linha-{index + 1}",
            message_date=message_date,
            source_path=source_path,
            work=work,
            product=type_name or product,
            type_name=type_name,
            piece=piece,
            section=section,
            length=length_text,
            dimensions=" ".join(item for item in (section, length_text) if item),
            unit_volume=unit_volume,
            status="PRONTO PARA REVISÃO" if not warnings else "CONFIRMAR",
            warnings=warnings,
            ocr_text=text,
        ))
    return drafts


def _parse_stake_delivery_text(
    text: str,
    *,
    message_id: str = "",
    message_date: str = "",
    source_path: str = "",
    group: str = "",
) -> list[LabelDraft]:
    """Parse the delivery-note table used for stakes.

    In this document the spreadsheet quantity is not the number of physical
    pieces.  It is the total from the printed ``Metros`` column.  Length and
    unit volume intentionally remain blank.
    """
    plain = _plain(text).upper()
    has_stake = bool(re.search(r"\b(?:E?STACA|STACA)\b", plain))
    required_markers = ("QUANTIDADE", "METROS")
    if not has_stake or not all(marker in plain for marker in required_markers):
        return []

    work_match = re.search(
        r"\bOBRA\s*:?\s*(.*?)\s+(?::?C?AMINHAO\b|CARRETA\b|MOTORISTA\b)",
        plain,
    )
    work = _clean(work_match.group(1)) if work_match else ""
    if not work:
        # Some delivery notes put the customer on the same line as ``OBRA``
        # and the city on the next one, without a CAMINHÃO marker nearby.
        # Keeping this fallback line-bounded avoids swallowing the whole OCR.
        line_match = re.search(r"(?:^|[\r\n])\s*OBRA\s*:?\s*([^\r\n]+)", text, re.IGNORECASE)
        if line_match:
            candidate = _clean(line_match.group(1))
            if candidate and len(candidate) <= 100:
                work = candidate

    dimensions = re.findall(r"\b\d{1,3}\s*[X×]\s*\d{1,3}\b", plain)
    dimension = ""
    if dimensions:
        normalized = [re.sub(r"\s*[X×]\s*", "X", value) for value in dimensions]
        dimension = Counter(normalized).most_common(1)[0][0]

    # OCR may flatten the table by columns in different orders.  Remove dates
    # and the delivery-note number, then use the largest standalone integer:
    # row lengths/quantities are smaller and the yellow total in `Metros` is
    # the largest integer (e.g. 32 + 20 -> 52). Decimal weights are excluded.
    numeric_area = re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", " ", plain)
    numeric_area = re.sub(r"\b(?:N|NO|NRO)\s*[.:\u00ba-]?\s*\d{3,}\b", " ", numeric_area)
    meter_values = [
        int(token) for token in re.findall(r"(?<![X\d.,])\b\d{1,3}\b(?![X\d.,])", numeric_area)
        if 0 < int(token) <= 1000
    ]
    total_meters: int | float | None = None
    if meter_values:
        total_meters = max(meter_values)

    warnings: list[str] = []
    for label, value in (
        ("obra", work),
        ("dimensão", dimension),
        ("metros totais", total_meters),
        ("data da mensagem", message_date),
    ):
        if value in ("", None):
            warnings.append(f"Confirmar {label}")

    return [LabelDraft(
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
        quantity=total_meters if total_meters is not None else 1,
        status="PRONTO PARA REVISÃO" if not warnings else "CONFIRMAR",
        warnings=warnings,
        ocr_text=text,
    )]


def parse_document_text(text: str, **metadata: str) -> list[LabelDraft]:
    stake_rows = _parse_stake_delivery_text(text, **metadata)
    if stake_rows:
        return stake_rows
    if "ROMANEIO DE CARGAS" in _plain(text).upper():
        rows = parse_romaneio_text(text, **metadata)
        if rows:
            return rows
    return [parse_label_text(text, **metadata)]
