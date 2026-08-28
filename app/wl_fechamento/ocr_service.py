from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps
import numpy as np

from .paddle_ocr_service import (
    is_available as paddle_available,
    read_line_texts as read_paddle_line_texts,
    read_text as read_paddle_text,
)


OCR_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "windows_ocr.ps1"
OCR_LAYOUT_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "windows_ocr_layout.ps1"
FIELD_WORDS = (
    "obra",
    "sigla",
    "produto",
    "secao",
    "comprimento",
    "peso",
    "peca",
    "volume",
    "vol",
)


@dataclass(frozen=True)
class OcrReading:
    text: str
    rotation: int
    score: int


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(character for character in decomposed if not unicodedata.combining(character)).lower()


def score_ocr_text(text: str) -> int:
    normalized = _normalize(text)
    keyword_score = sum(12 for word in FIELD_WORDS if re.search(rf"\b{re.escape(word)}\b", normalized))
    # A good label reading has several explicit field markers.  Digits alone
    # are not evidence of a correct reading (QR codes and weights contain many
    # digits), so they receive only a small secondary weight.
    marker_score = min(len(re.findall(r"\b(?:obra|sigla|produto|secao|comprimento|peso|peca|vol(?:ume)?)\b\s*[:.]?", normalized)) * 8, 64)
    digit_score = min(sum(character.isdigit() for character in text), 40)
    return keyword_score + marker_score + digit_score // 2 + min(len(text) // 40, 15)


def _prepare_variant(source: Image.Image, rotation: int) -> Image.Image:
    image = ImageOps.exif_transpose(source).rotate(rotation, expand=True)
    longest = max(image.size)
    if longest < 2200:
        scale = 2200 / longest
        image = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
            Image.Resampling.LANCZOS,
        )
    gray = ImageOps.autocontrast(ImageOps.grayscale(image), cutoff=1)
    gray = ImageEnhance.Sharpness(gray).enhance(1.8)
    return gray.convert("RGB")


def _orange_label_crop(source: Image.Image) -> Image.Image | None:
    crops = _orange_label_crops(source)
    if crops:
        return max(crops, key=lambda item: item.width * item.height)
    return None


def _orange_mask(pixels: np.ndarray) -> np.ndarray:
    """Detect the printed orange frame in both daylight and dim warehouses."""
    red, green, blue = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    red_green = red.astype(np.int16) - green.astype(np.int16)
    green_blue = green.astype(np.int16) - blue.astype(np.int16)
    strict = (
        (red > 170)
        & (green > 45)
        & (green < 190)
        & (blue < 125)
        & (red_green > 45)
    )
    if int(strict.sum()) >= 500:
        return strict
    # Phone exposure can lower the same orange border to roughly RGB
    # 145/70/20.  Requiring green to remain above blue separates that border
    # from the red handwritten markings commonly present on the concrete.
    return (
        (red > 120)
        & (green > 25)
        & (green < 160)
        & (blue < 100)
        & (red_green > 35)
        & (green_blue > 15)
    )


def _orange_label_crops(source: Image.Image) -> list[Image.Image]:
    """Return separate orange-bordered labels, including fragmented frames."""
    rgb = ImageOps.exif_transpose(source).convert("RGB")
    pixels = np.asarray(rgb)
    mask = _orange_mask(pixels)
    y_values, x_values = np.where(mask)
    if len(x_values) < 500:
        return []
    boxes: list[tuple[int, int, int, int]] = []
    try:
        vendor = Path(r"C:\WLAppRuntime\vendor_ocr")
        if str(vendor) not in sys.path:
            sys.path.insert(0, str(vendor))
        import cv2

        binary = mask.astype(np.uint8) * 255
        kernel_size = max(15, round(min(rgb.size) * 0.025))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        parts = [
            tuple(map(int, cv2.boundingRect(contour)))
            for contour in contours
            if cv2.contourArea(contour) >= 300
        ]
        # Damaged borders often appear as top, bottom and side fragments.
        # Merge fragments whose projections overlap and whose gap is smaller
        # than the expected label size, without joining adjacent labels.
        changed = True
        while changed:
            changed = False
            merged: list[tuple[int, int, int, int]] = []
            while parts:
                x, y, width, height = parts.pop()
                right, bottom = x + width, y + height
                index = 0
                while index < len(parts):
                    ox, oy, ow, oh = parts[index]
                    oright, obottom = ox + ow, oy + oh
                    overlap_x = max(0, min(right, oright) - max(x, ox))
                    overlap_y = max(0, min(bottom, obottom) - max(y, oy))
                    gap_x = max(0, max(x, ox) - min(right, oright))
                    gap_y = max(0, max(y, oy) - min(bottom, obottom))
                    fragmentary = (
                        min(width, height) <= max(width, height) * 0.4
                        or min(ow, oh) <= max(ow, oh) * 0.4
                    )
                    near_vertical = fragmentary and overlap_x >= min(width, ow) * 0.2 and gap_y <= max(width, ow) * 0.9
                    near_horizontal = fragmentary and overlap_y >= min(height, oh) * 0.2 and gap_x <= max(height, oh) * 0.9
                    if near_vertical or near_horizontal:
                        x, y = min(x, ox), min(y, oy)
                        right, bottom = max(right, oright), max(bottom, obottom)
                        width, height = right - x, bottom - y
                        parts.pop(index)
                        changed = True
                    else:
                        index += 1
                merged.append((x, y, width, height))
            parts = merged
        boxes = parts
    except Exception:
        boxes = []
    padding = max(12, round(min(rgb.size) * 0.02))
    results: list[Image.Image] = []
    filtered_boxes: list[tuple[int, int, int, int]] = []
    for candidate in sorted(boxes, key=lambda item: item[2] * item[3], reverse=True):
        x, y, width, height = candidate
        area = width * height
        duplicate = False
        for ox, oy, ow, oh in filtered_boxes:
            intersection = max(0, min(x + width, ox + ow) - max(x, ox)) * max(
                0, min(y + height, oy + oh) - max(y, oy)
            )
            if area and intersection / area >= 0.5:
                duplicate = True
                break
        if not duplicate:
            filtered_boxes.append(candidate)
    for x, y, width, height in filtered_boxes:
        if width * height < rgb.width * rgb.height * 0.035:
            continue
        box = (
            max(0, x - padding), max(0, y - padding),
            min(rgb.width, x + width + padding), min(rgb.height, y + height + padding),
        )
        results.append(rgb.crop(box))
    if results:
        return sorted(results, key=lambda item: item.width * item.height, reverse=True)
    # Conservative fallback used when OpenCV is unavailable.
    box = (
        max(0, int(x_values.min()) - padding),
        max(0, int(y_values.min()) - padding),
        min(rgb.width, int(x_values.max()) + padding + 1),
        min(rgb.height, int(y_values.max()) + padding + 1),
    )
    if (box[2] - box[0]) * (box[3] - box[1]) < rgb.width * rgb.height * 0.05:
        return []
    return [rgb.crop(box)]


def _rectify_label(label: Image.Image) -> Image.Image:
    """Deskew/perspective-correct a cropped orange-bordered label.

    Phone photos are commonly taken from above or from one side.  A plain
    bounding box leaves the printed rows slanted, which is enough for OCR to
    drop the last digit of a section or split the volume from its label.
    """
    rgb = label.convert("RGB")
    try:
        vendor = Path(r"C:\WLAppRuntime\vendor_ocr")
        if str(vendor) not in sys.path:
            sys.path.insert(0, str(vendor))
        import cv2

        pixels = np.asarray(rgb)
        mask = _orange_mask(pixels)
        ys, xs = np.where(mask)
        if len(xs) < 250:
            return rgb
        points = np.column_stack((xs, ys)).astype(np.float32)
        hull = cv2.convexHull(points.reshape(-1, 1, 2))
        perimeter = cv2.arcLength(hull, True)
        polygon = cv2.approxPolyDP(hull, 0.025 * perimeter, True)
        if len(polygon) == 4:
            corners = polygon.reshape(4, 2).astype(np.float32)
        else:
            corners = cv2.boxPoints(cv2.minAreaRect(points)).astype(np.float32)

        sums = corners.sum(axis=1)
        differences = np.diff(corners, axis=1).reshape(-1)
        ordered = np.array(
            [
                corners[np.argmin(sums)],
                corners[np.argmin(differences)],
                corners[np.argmax(sums)],
                corners[np.argmax(differences)],
            ],
            dtype=np.float32,
        )
        top_left, top_right, bottom_right, bottom_left = ordered
        width = int(max(np.linalg.norm(top_right - top_left), np.linalg.norm(bottom_right - bottom_left)))
        height = int(max(np.linalg.norm(bottom_left - top_left), np.linalg.norm(bottom_right - top_right)))
        if width < 120 or height < 70:
            return rgb
        ratio = max(width, height) / max(1, min(width, height))
        if ratio < 1.25 or ratio > 4.5:
            return rgb
        destination = np.array(
            [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
            dtype=np.float32,
        )
        matrix = cv2.getPerspectiveTransform(ordered, destination)
        warped = cv2.warpPerspective(pixels, matrix, (width, height), borderMode=cv2.BORDER_REPLICATE)
        return Image.fromarray(warped).convert("RGB")
    except Exception:
        return rgb


def _prepare_paddle_label(label: Image.Image) -> Image.Image:
    """Enlarge small phone-photo labels before neural OCR.

    Many WhatsApp photos are 1080x1920 while the label itself is only about
    150 pixels wide.  OCR cannot recover characters that remain that small,
    even when the label was correctly detected.  Upscaling the isolated label
    before orientation/unwarping gives the recognizer enough pixels without
    magnifying concrete texture from the rest of the photo.
    """
    image = _rectify_label(label)
    if image.height > image.width:
        image = image.rotate(90, expand=True)
    longest = max(image.size)
    if longest < 400:
        scale = 400 / longest
        image = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
            Image.Resampling.LANCZOS,
        )
    image = ImageOps.autocontrast(image, cutoff=1)
    image = ImageEnhance.Contrast(image).enhance(1.15)
    image = ImageEnhance.Sharpness(image).enhance(1.6)
    return image


def _read_variant(path: Path) -> str:
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(OCR_SCRIPT),
            "-Path",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8-sig",
        errors="replace",
        timeout=45,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(detail or "O OCR local não conseguiu ler a imagem.")
    lines = completed.stdout.strip().splitlines()
    if not lines:
        return ""
    try:
        return base64.b64decode(lines[-1]).decode("utf-8", errors="replace").strip()
    except (ValueError, TypeError):
        return ""


def _read_layout(path: Path) -> dict:
    completed = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(OCR_LAYOUT_SCRIPT), "-Path", str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8-sig",
        errors="replace",
        timeout=45,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(detail or "O OCR de layout não conseguiu ler a imagem.")
    lines = completed.stdout.strip().splitlines()
    if not lines:
        return {"text": "", "lines": []}
    try:
        decoded = base64.b64decode(lines[-1]).decode("utf-8", errors="replace")
        payload = json.loads(decoded)
        return payload if isinstance(payload, dict) else {"text": "", "lines": []}
    except (ValueError, TypeError, json.JSONDecodeError):
        return {"text": "", "lines": []}


def _domain_warning_count(text: str) -> int:
    from .label_parser import parse_document_text

    return sum(
        1 for draft in parse_document_text(text)
        for warning in draft.warnings
        if warning != "Confirmar data da mensagem"
    )


def _read_layout_assisted(source: Image.Image, temporary_path: Path) -> tuple[str, float]:
    """Detect rows quickly, then run accurate recognition only on those rows."""
    label = _orange_label_crop(source) or ImageOps.exif_transpose(source).convert("RGB")
    label = _rectify_label(label)
    if label.height > label.width:
        label = label.rotate(90, expand=True)
    prepared = _prepare_variant(label, 0)
    page_path = temporary_path / "layout_page.png"
    prepared.save(page_path, format="PNG", optimize=True)
    layout = _read_layout(page_path)
    original_text = str(layout.get("text") or "").strip()
    rows = layout.get("lines") if isinstance(layout.get("lines"), list) else []
    from .label_parser import parse_document_text
    pending_labels = {
        warning.lower().replace("confirmar ", "", 1)
        for draft in parse_document_text(original_text)
        for warning in draft.warnings
        if warning != "Confirmar data da mensagem"
    }
    keyword_map = {
        "obra": ("obra",),
        "produto": ("produto",),
        "tipo normalizado": ("produto", "comprimento"),
        "peça": ("peca", "peça"),
        "seção": ("secao", "seção"),
        "comprimento": ("comprimento",),
        "volume unitário": ("vol", "volume"),
    }
    target_keywords = {
        keyword
        for label_name in pending_labels
        for keyword in keyword_map.get(label_name, ())
    }
    row_paths: list[Path] = []

    def save_line_variants(strip: Image.Image, stem: str, target_height: int) -> None:
        """Save complementary views of one printed row for OCR ensembling."""
        scale = target_height / max(1, strip.height)
        resized = strip.resize(
            (max(1, round(strip.width * scale)), target_height),
            Image.Resampling.LANCZOS,
        )
        gray = ImageOps.autocontrast(ImageOps.grayscale(resized), cutoff=1)
        variants: list[tuple[str, Image.Image]] = [
            ("gray", ImageOps.expand(gray, border=10, fill=255).convert("RGB")),
            (
                "contrast",
                ImageOps.expand(
                    ImageEnhance.Contrast(gray).enhance(1.8), border=10, fill=255
                ).convert("RGB"),
            ),
        ]
        try:
            vendor = Path(r"C:\WLAppRuntime\vendor_ocr")
            if str(vendor) not in sys.path:
                sys.path.insert(0, str(vendor))
            import cv2

            array = np.asarray(gray)
            block_size = max(15, min(51, (target_height // 3) | 1))
            adaptive = cv2.adaptiveThreshold(
                array,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                block_size,
                11,
            )
            variants.append(
                (
                    "adaptive",
                    ImageOps.expand(Image.fromarray(adaptive), border=10, fill=255).convert("RGB"),
                )
            )
        except Exception:
            pass
        for suffix, variant in variants:
            path = temporary_path / f"{stem}_{suffix}.png"
            variant.save(path, format="PNG", optimize=True)
            row_paths.append(path)
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        row_text = _normalize(str(row.get("text") or ""))
        if target_keywords and not any(keyword in row_text for keyword in target_keywords):
            continue
        try:
            x = max(0, int(float(row.get("x", 0))))
            y = max(0, int(float(row.get("y", 0))))
            width = max(1, int(float(row.get("width", 0))))
            height = max(1, int(float(row.get("height", 0))))
        except (TypeError, ValueError):
            continue
        if height < 6:
            continue
        pad_y = max(8, round(height * 0.65))
        pad_x = max(10, round(height * 0.4))
        box = (
            max(0, x - pad_x),
            max(0, y - pad_y),
            min(prepared.width, x + width + round(height * 12)),
            min(prepared.height, y + height + pad_y),
        )
        strip = prepared.crop(box)
        save_line_variants(strip, f"layout_row_{index:02d}", 160)
    # Printed Prellog labels use a stable vertical layout. If the fast OCR
    # omitted an entire row (common for italic `Seção:`), add a normalized
    # template strip for that pending field. These are relative coordinates,
    # so they work after the orange frame has been isolated and rotated.
    template_bands = {
        "obra": ((0.30, 0.40, 0.02, 0.98), (0.22, 0.34, 0.02, 0.98)),
        "produto": ((0.47, 0.55, 0.02, 0.82), (0.38, 0.49, 0.02, 0.82)),
        "tipo normalizado": ((0.47, 0.55, 0.02, 0.90),),
        # Two narrow alternatives cover small variations in frame padding.
        # Narrow single-line crops outperform one tall multi-line crop in the
        # recognition model, especially for the final digit and decimal comma.
        "seção": ((0.52, 0.61, 0.02, 0.76), (0.56, 0.64, 0.02, 0.76)),
        "comprimento": ((0.59, 0.68, 0.02, 0.84), (0.63, 0.71, 0.02, 0.84)),
        "volume unitário": ((0.64, 0.73, 0.46, 0.99), (0.68, 0.78, 0.46, 0.99)),
        "peça": ((0.76, 0.86, 0.02, 0.76), (0.80, 0.91, 0.02, 0.76)),
    }
    for index, label_name in enumerate(sorted(pending_labels)):
        bands = template_bands.get(label_name)
        if bands is None:
            continue
        for band_index, band in enumerate(bands):
            top, bottom, left, right = band
            box = (
                round(prepared.width * left), round(prepared.height * top),
                round(prepared.width * right), round(prepared.height * bottom),
            )
            strip = prepared.crop(box)
            save_line_variants(
                strip,
                f"template_{index:02d}_{band_index}_{label_name.replace(' ', '_')}",
                128,
            )
    if not row_paths:
        return original_text, 0.0
    recognized = read_paddle_line_texts(row_paths, quality="medium")
    # Put the most confident alternative first and remove repeated readings.
    # The domain parser then rejects malformed sections, QR/weight values and
    # other numerically plausible but contextually wrong tokens.
    neural_lines: list[str] = []
    for text, confidence in sorted(recognized, key=lambda item: item[1], reverse=True):
        if text and confidence >= 0.35 and text not in neural_lines:
            neural_lines.append(text)
    neural_text = "\n".join(neural_lines).strip()
    if not neural_text:
        return original_text, 0.0
    # Keep the fast OCR text as well: one engine may read the section while
    # the other reads the length. The parser resolves explicit labels and
    # rejects conflicts/implausible values field by field.
    merged_text = "\n".join(part for part in (original_text, neural_text) if part)
    candidates = (original_text, neural_text, merged_text)
    best_text = min(candidates, key=_domain_warning_count)
    if _domain_warning_count(best_text) <= _domain_warning_count(original_text):
        confidence = sum(score for _, score in recognized) / max(1, len(recognized))
        return best_text, confidence
    return original_text, 0.0


def read_image_text(
    image_path: Path,
    rotations: tuple[int, ...] = (0, 90, 180, 270),
) -> OcrReading:
    if paddle_available():
        try:
            # Restrict OCR to the orange-bordered factory label whenever it
            # can be detected.  This removes handwritten markings, concrete
            # texture and QR-code noise before recognition.  If the crop does
            # not contain enough field markers, retry the complete photo.
            paddle_path = image_path
            with Image.open(image_path) as paddle_source, tempfile.TemporaryDirectory(prefix="wl_paddle_") as temporary:
                layout_text, layout_confidence = _read_layout_assisted(
                    paddle_source,
                    Path(temporary),
                )
                layout_warning_count = _domain_warning_count(layout_text)
                if layout_text and layout_warning_count <= 1:
                    return OcrReading(
                        text=layout_text,
                        rotation=0,
                        score=score_ocr_text(layout_text) + round(layout_confidence * 100),
                    )
                label = _orange_label_crop(paddle_source)
                if label is not None:
                    paddle_path = Path(temporary) / "etiqueta.png"
                    _prepare_paddle_label(label).save(paddle_path, format="PNG", optimize=True)
                small_text, small_confidence = read_paddle_text(paddle_path, quality="small")
                from .label_parser import parse_document_text

                small_drafts = parse_document_text(small_text)
                small_warning_count = sum(
                    1
                    for draft in small_drafts
                    for warning in draft.warnings
                    if warning != "Confirmar data da mensagem"
                )
                text, confidence = small_text, small_confidence
                if layout_text and layout_warning_count < small_warning_count:
                    text, confidence = layout_text, layout_confidence
                    small_warning_count = layout_warning_count
                field_score = score_ocr_text(text)
                # Easy labels finish with the light model. Any unresolved
                # field is re-read by the accurate model, and the parser—not
                # raw OCR confidence—decides which candidate is more complete.
                if small_warning_count or small_confidence < 0.75:
                    medium_text, medium_confidence = read_paddle_text(paddle_path, quality="medium")
                    medium_drafts = parse_document_text(medium_text)
                    medium_warning_count = sum(
                        1
                        for draft in medium_drafts
                        for warning in draft.warnings
                        if warning != "Confirmar data da mensagem"
                    )
                    if (
                        medium_warning_count < small_warning_count
                        or (
                            medium_warning_count == small_warning_count
                            and medium_confidence > small_confidence
                        )
                    ):
                        text, confidence = medium_text, medium_confidence
                        field_score = score_ocr_text(text)
            # Even a low average confidence can contain several correct label
            # fields.  The domain parser validates every value separately and
            # leaves only missing/implausible fields pending.  Falling back to
            # four full-photo Windows OCR rotations here was both slower and
            # less accurate on the WhatsApp labels.
            if text.strip():
                return OcrReading(
                    text=text,
                    rotation=0,
                    score=field_score + round(confidence * 100),
                )
        except Exception:
            # Keep the Windows OCR as an offline fallback if PaddleOCR cannot
            # initialize or a model fails on a particular image.
            pass
    if not OCR_SCRIPT.exists():
        raise RuntimeError("O componente local de OCR não foi localizado.")
    readings: list[OcrReading] = []
    with Image.open(image_path) as source, tempfile.TemporaryDirectory(prefix="wl_ocr_") as temporary:
        temporary_path = Path(temporary)
        prepared_source = _orange_label_crop(source) or ImageOps.exif_transpose(source).convert("RGB")
        for rotation in rotations:
            variant = _prepare_variant(prepared_source, rotation)
            variant_path = temporary_path / f"rotation_{rotation}.png"
            variant.save(variant_path, format="PNG", optimize=True)
            text = _read_variant(variant_path)
            reading = OcrReading(text=text, rotation=rotation, score=score_ocr_text(text))
            readings.append(reading)
            # Do not stop at the first high-scoring OCR result.  QR codes,
            # weights and random digits can score highly while the label is
            # rotated or fields are misplaced.  All orientations are compared
            # before choosing the result.
    return max(readings, key=lambda item: item.score)


def read_image_text_targeted(image_path: Path) -> OcrReading:
    """Accurate second pass for labels that still have unresolved fields.

    Compare the row-assisted reading with a complete PP-OCRv6 reading of the
    rectified label.  Merging both outputs is intentional: the full detector
    often sees a faint last digit while the targeted rows preserve explicit
    field labels.  The domain parser chooses the candidate with fewer missing
    or implausible fields.
    """
    if not paddle_available():
        return read_image_text(image_path)
    with Image.open(image_path) as source, tempfile.TemporaryDirectory(prefix="wl_targeted_") as temporary:
        temporary_path = Path(temporary)
        layout_text, layout_confidence = _read_layout_assisted(source, temporary_path)
        # Skip the full detector only when the focused pass is already nearly
        # complete.  Returning with three unresolved fields caused clearly
        # visible labels (such as VPT-2) to remain pending without ever being
        # read by the full PP-OCRv6 detector.
        if layout_text and _domain_warning_count(layout_text) == 0:
            return OcrReading(
                text=layout_text,
                rotation=0,
                score=score_ocr_text(layout_text) + round(layout_confidence * 100),
            )
        label = _orange_label_crop(source)
        full_text = ""
        full_confidence = 0.0
        if label is not None:
            label_path = temporary_path / "etiqueta_retificada.png"
            _prepare_paddle_label(label).save(label_path, format="PNG", optimize=True)
            full_text, full_confidence = read_paddle_text(label_path, quality="medium")
        merged_text = "\n".join(part for part in (layout_text, full_text) if part)
        candidates = [candidate for candidate in (layout_text, full_text, merged_text) if candidate.strip()]
        text = min(candidates, key=lambda candidate: (_domain_warning_count(candidate), -score_ocr_text(candidate))) if candidates else ""
        confidence = max(layout_confidence, full_confidence)
    return OcrReading(
        text=text,
        rotation=0,
        score=score_ocr_text(text) + round(confidence * 100),
    )


def read_image_texts(image_path: Path) -> list[OcrReading]:
    """Read each distinct factory label visible in the same photograph."""
    with Image.open(image_path) as source:
        crops = _orange_label_crops(source)
    if len(crops) <= 1:
        return [read_image_text(image_path)]
    readings: list[OcrReading] = []
    with tempfile.TemporaryDirectory(prefix="wl_labels_") as temporary:
        temporary_path = Path(temporary)
        for index, crop in enumerate(crops, start=1):
            crop_path = temporary_path / f"etiqueta_{index}.png"
            crop.save(crop_path, format="PNG", optimize=True)
            readings.append(read_image_text(crop_path))
    return readings
