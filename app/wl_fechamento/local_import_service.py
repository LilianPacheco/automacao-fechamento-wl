from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from .config import configuration_directory
from .stake_parser import parse_stake_text
from .whatsapp_service import (
    WhatsAppAttachment,
    WhatsAppEvidence,
    WhatsAppProbeResult,
)


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
IGNORED_IMAGE_DIRECTORIES = {
    "analise_visual_v2", "analise_visual", "ocr", "crops", "recortes", "cache"
}
MESSAGE_PATTERNS = (
    re.compile(
        r"^[\u200e\u200f]*\[?(?P<date>\d{1,2}/\d{1,2}/\d{2,4})"
        r"[, ]+(?P<time>\d{1,2}:\d{2})(?::\d{2})?\]?\s*(?:[-–]\s*)?"
        r"(?P<sender>[^:]+):\s*(?P<body>.*)$"
    ),
    re.compile(
        r"^[\u200e\u200f]*(?P<date>\d{1,2}/\d{1,2}/\d{2,4})"
        r"[, ]+(?P<time>\d{1,2}:\d{2})(?::\d{2})?\s*[-–]\s*"
        r"(?P<sender>[^:]+):\s*(?P<body>.*)$"
    ),
)


@dataclass
class ExportedMessage:
    message_date: str
    message_time: str
    sender: str
    body: str


def _normalized_date(raw: str) -> str:
    day, month, year = (int(part) for part in raw.split("/"))
    if year < 100:
        year += 2000
    return date(year, month, day).strftime("%d/%m/%Y")


def parse_exported_chat(text: str) -> list[ExportedMessage]:
    messages: list[ExportedMessage] = []
    for raw_line in text.splitlines():
        line = raw_line.strip("\ufeff")
        match = next((pattern.match(line) for pattern in MESSAGE_PATTERNS if pattern.match(line)), None)
        if match:
            try:
                message_date = _normalized_date(match.group("date"))
            except (ValueError, TypeError):
                continue
            messages.append(ExportedMessage(
                message_date=message_date,
                message_time=match.group("time"),
                sender=match.group("sender").strip(),
                body=match.group("body").strip(),
            ))
        elif messages and line.strip():
            messages[-1].body += "\n" + line.strip()
    return messages


def _safe_extract(archive: Path, destination: Path) -> None:
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive) as zipped:
        for member in zipped.infolist():
            target = (destination / member.filename).resolve()
            if destination_root != target and destination_root not in target.parents:
                raise RuntimeError("O ZIP contém um caminho de arquivo inseguro.")
        zipped.extractall(destination)


def _date_from_filename_or_file(path: Path, start: date, end: date) -> str:
    compact = re.search(r"(?<!\d)(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?!\d)", path.name)
    if compact:
        try:
            candidate = date(int(compact.group(1)), int(compact.group(2)), int(compact.group(3)))
            if start <= candidate <= end:
                return candidate.strftime("%d/%m/%Y")
        except ValueError:
            pass
    modified = datetime.fromtimestamp(path.stat().st_mtime).date()
    return modified.strftime("%d/%m/%Y") if start <= modified <= end else ""


def _quantity_from_body(body: str) -> tuple[str, int | float | None]:
    for token in re.findall(r"\d{1,3}\s*[xX×]\s*\d{1,3}(?:\s*[xX×]\s*\d{1,3})?\s*(?:[=+]\s*\d+)?", body):
        try:
            parsed = parse_stake_text(token)
            return token, parsed.quantity
        except ValueError:
            continue
    return "", None


def import_local_evidence(
    source: str | Path,
    start_date: date,
    end_date: date,
    captures_root: Path | None = None,
) -> WhatsAppProbeResult:
    source_path = Path(source).expanduser().resolve()
    if not source_path.exists():
        raise RuntimeError("A pasta ou o ZIP selecionado não existe.")

    with tempfile.TemporaryDirectory(prefix="wl_evidencias_") as temporary:
        if source_path.is_file():
            if source_path.suffix.lower() != ".zip":
                raise RuntimeError("Selecione um arquivo ZIP exportado pelo WhatsApp.")
            scan_root = Path(temporary) / "extraido"
            scan_root.mkdir()
            _safe_extract(source_path, scan_root)
        else:
            scan_root = source_path

        images = sorted(
            path for path in scan_root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in IMAGE_SUFFIXES
            and not any(
                part.casefold() in IGNORED_IMAGE_DIRECTORIES
                for part in path.relative_to(scan_root).parts[:-1]
            )
        )
        if not images:
            raise RuntimeError("Nenhuma foto JPG, PNG ou WEBP foi encontrada.")

        text_files = sorted(path for path in scan_root.rglob("*.txt") if path.is_file())
        messages: list[ExportedMessage] = []
        for text_file in text_files:
            for encoding in ("utf-8-sig", "utf-16", "latin-1"):
                try:
                    messages = parse_exported_chat(text_file.read_text(encoding=encoding))
                    if messages:
                        break
                except (UnicodeError, OSError):
                    continue
            if messages:
                break

        saved_evidences: list[WhatsAppEvidence] = []
        session_files = sorted(scan_root.rglob("sessao_whatsapp.json"))
        if session_files:
            try:
                payload = json.loads(session_files[0].read_text(encoding="utf-8"))
                saved_evidences = WhatsAppProbeResult.from_dict(payload).evidences
            except (OSError, ValueError, TypeError):
                saved_evidences = []

        period_messages = []
        for message in messages:
            parsed_date = datetime.strptime(message.message_date, "%d/%m/%Y").date()
            if start_date <= parsed_date <= end_date:
                period_messages.append(message)

        capture_dir = (
            (captures_root or configuration_directory() / "Capturas")
            / f"local_{start_date:%Y%m%d}_{end_date:%Y%m%d}_{uuid.uuid4().hex[:10]}"
        )
        capture_dir.mkdir(parents=True, exist_ok=False)
        actual_by_name = {path.name.casefold(): path for path in images}
        assigned: set[Path] = set()
        evidence_rows: list[WhatsAppEvidence] = []
        attachment_rows: list[WhatsAppAttachment] = []
        seen_hashes: set[str] = set()

        def copy_attachment(path: Path, message_id: str) -> bool:
            content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if content_hash in seen_hashes:
                return False
            seen_hashes.add(content_hash)
            destination = capture_dir / f"{message_id}_{content_hash[:12]}{path.suffix.lower()}"
            shutil.copy2(path, destination)
            attachment_rows.append(WhatsAppAttachment(
                message_id=message_id,
                filename=path.name,
                mime_type=mimetypes.guess_type(path.name)[0] or "image/jpeg",
                path=str(destination),
                size=destination.stat().st_size,
                sha256=content_hash,
            ))
            assigned.add(path)
            return True

        for index, saved in enumerate(saved_evidences, start=1):
            try:
                saved_date = datetime.strptime(saved.message_date, "%d/%m/%Y").date()
            except ValueError:
                continue
            if not start_date <= saved_date <= end_date:
                continue
            referenced = [
                path for path in images
                if path.name.casefold().startswith(f"{saved.message_id}_".casefold())
            ]
            if not referenced:
                continue
            message_id = f"local-salva-{index:05d}"
            copied = sum(copy_attachment(path, message_id) for path in referenced)
            if copied:
                evidence_rows.append(WhatsAppEvidence(
                    message_id=message_id,
                    message_date=saved.message_date,
                    message_time=saved.message_time,
                    sender=saved.sender,
                    image_count=copied,
                    stake_text=saved.stake_text,
                    quantity_hint=saved.quantity_hint,
                ))

        for index, message in enumerate(period_messages, start=1):
            referenced = [
                path for name, path in actual_by_name.items()
                if path not in assigned and name in message.body.casefold()
            ]
            if not referenced:
                continue
            message_id = f"local-msg-{index:05d}"
            copied = sum(copy_attachment(path, message_id) for path in referenced)
            if not copied:
                continue
            stake_text, quantity = _quantity_from_body(message.body)
            evidence_rows.append(WhatsAppEvidence(
                message_id=message_id,
                message_date=message.message_date,
                message_time=message.message_time,
                sender=message.sender,
                image_count=copied,
                stake_text=stake_text,
                quantity_hint=quantity,
            ))

        for index, image in enumerate(images, start=1):
            if image in assigned:
                continue
            message_id = f"local-foto-{index:05d}"
            if not copy_attachment(image, message_id):
                continue
            evidence_rows.append(WhatsAppEvidence(
                message_id=message_id,
                message_date=_date_from_filename_or_file(image, start_date, end_date),
                image_count=1,
            ))

        if not attachment_rows:
            raise RuntimeError("As fotos encontradas eram duplicadas ou não puderam ser copiadas.")
        missing_dates = sum(not item.message_date for item in evidence_rows)
        message = (
            f"Importação local concluída: {len(attachment_rows)} foto(s) únicas. "
            f"{missing_dates} foto(s) ficaram com a data pendente para confirmação."
        )
        result = WhatsAppProbeResult(
            connected=True,
            group_found=True,
            start_date_found=True,
            start_date=start_date.strftime("%d/%m/%Y"),
            period_scan_complete=True,
            group_name="Pasta ou ZIP local",
            visible_images=len(images),
            evidences=evidence_rows,
            captured_attachments=attachment_rows,
            incomplete_albums=[],
            message=message,
        )
        (capture_dir / "sessao_whatsapp.json").write_text(
            json.dumps(asdict(result), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result
