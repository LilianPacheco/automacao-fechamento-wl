from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .config import configuration_directory

GROUP_NAME = "AWL x Expedição Prellog"
NODE_EXECUTABLE = Path(
    r"C:\Users\lilia\.cache\codex-runtimes\codex-primary-runtime"
    r"\dependencies\node\bin\node.exe"
)
NODE_MODULES = Path(
    r"C:\Users\lilia\.cache\codex-runtimes\codex-primary-runtime"
    r"\dependencies\node\node_modules"
)
PROBE_SCRIPT = Path(__file__).resolve().parents[1] / "browser" / "whatsapp_probe.js"


@dataclass(frozen=True)
class WhatsAppEvidence:
    message_id: str
    message_date: str
    message_time: str = ""
    sender: str = ""
    image_count: int = 0
    pdf_names: list[str] = field(default_factory=list)
    stake_text: str = ""
    quantity_hint: int | float | None = None
    has_ok: bool = False

    @property
    def kind_label(self) -> str:
        parts: list[str] = []
        if self.image_count:
            parts.append(
                f"{self.image_count} foto" if self.image_count == 1
                else f"{self.image_count} fotos"
            )
        if self.pdf_names:
            parts.append(
                f"{len(self.pdf_names)} PDF" if len(self.pdf_names) == 1
                else f"{len(self.pdf_names)} PDFs"
            )
        if self.stake_text:
            parts.append("Estaca")
        return ", ".join(parts) or "evidência"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WhatsAppEvidence":
        quantity_hint: int | float | None = None
        try:
            parsed_quantity = float(data.get("quantity_hint"))
            if parsed_quantity > 0:
                quantity_hint = (
                    int(parsed_quantity)
                    if parsed_quantity.is_integer()
                    else round(parsed_quantity, 3)
                )
        except (TypeError, ValueError):
            pass
        return cls(
            message_id=str(data.get("message_id", "")),
            message_date=str(data.get("message_date", "")),
            message_time=str(data.get("message_time", "")),
            sender=str(data.get("sender", "")),
            image_count=max(0, int(data.get("image_count", 0))),
            pdf_names=[str(item) for item in data.get("pdf_names", [])],
            stake_text=str(data.get("stake_text", "")),
            quantity_hint=quantity_hint,
            has_ok=bool(data.get("has_ok")),
        )


@dataclass(frozen=True)
class WhatsAppAttachment:
    message_id: str
    filename: str
    mime_type: str
    path: str
    size: int
    sha256: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WhatsAppAttachment":
        return cls(
            message_id=str(data.get("message_id", "")),
            filename=str(data.get("filename", "")),
            mime_type=str(data.get("mime_type", "application/octet-stream")),
            path=str(data.get("path", "")),
            size=max(0, int(data.get("size", 0))),
            sha256=str(data.get("sha256", "")),
        )


@dataclass(frozen=True)
class WhatsAppAlbumStatus:
    message_id: str
    expected: int
    captured: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WhatsAppAlbumStatus":
        return cls(
            message_id=str(data.get("message_id", "")),
            expected=max(0, int(data.get("expected", 0))),
            captured=max(0, int(data.get("captured", 0))),
        )


@dataclass(frozen=True)
class WhatsAppProbeResult:
    connected: bool
    group_found: bool
    start_date_found: bool
    start_date: str
    period_scan_complete: bool = False
    group_name: str = GROUP_NAME
    load_attempts: int = 0
    sync_waits: int = 0
    sync_in_progress: bool = False
    visible_images: int = 0
    visible_pdfs: int = 0
    ok_reactions: int = 0
    stake_messages: list[str] = field(default_factory=list)
    evidences: list[WhatsAppEvidence] = field(default_factory=list)
    captured_attachments: list[WhatsAppAttachment] = field(default_factory=list)
    incomplete_albums: list[WhatsAppAlbumStatus] = field(default_factory=list)
    evidence_truncated: bool = False
    message: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WhatsAppProbeResult":
        return cls(
            connected=bool(data.get("connected")),
            group_found=bool(data.get("group_found")),
            start_date_found=bool(data.get("start_date_found")),
            start_date=str(data.get("start_date", "")),
            period_scan_complete=bool(data.get("period_scan_complete")),
            group_name=str(data.get("group_name", GROUP_NAME)),
            load_attempts=int(data.get("load_attempts", 0)),
            sync_waits=int(data.get("sync_waits", 0)),
            sync_in_progress=bool(data.get("sync_in_progress")),
            visible_images=int(data.get("visible_images", 0)),
            visible_pdfs=int(data.get("visible_pdfs", 0)),
            ok_reactions=int(data.get("ok_reactions", 0)),
            stake_messages=[str(item) for item in data.get("stake_messages", [])],
            evidences=[
                WhatsAppEvidence.from_dict(item)
                for item in data.get("evidences", [])
                if isinstance(item, dict)
            ],
            captured_attachments=[
                WhatsAppAttachment.from_dict(item)
                for item in data.get("captured_attachments", [])
                if isinstance(item, dict)
            ],
            incomplete_albums=[
                WhatsAppAlbumStatus.from_dict(item)
                for item in data.get("incomplete_albums", [])
                if isinstance(item, dict)
            ],
            evidence_truncated=bool(data.get("evidence_truncated")),
            message=str(data.get("message", "")),
        )


def restrict_result_to_period(
    result: WhatsAppProbeResult,
    start_date: date,
    end_date: date,
) -> WhatsAppProbeResult:
    """Keep only evidence and attachments proven to belong to the selection.

    The browser reader is expected to filter the period already.  This second
    boundary prevents a stale or mixed browser payload from ever reaching OCR.
    """
    valid_evidences: list[WhatsAppEvidence] = []
    for evidence in result.evidences:
        try:
            evidence_date = datetime.strptime(evidence.message_date, "%d/%m/%Y").date()
        except ValueError:
            continue
        if start_date <= evidence_date <= end_date:
            valid_evidences.append(evidence)

    valid_ids = [evidence.message_id for evidence in valid_evidences]

    def belongs_to_valid_evidence(message_id: str) -> bool:
        return any(
            message_id == evidence_id
            or message_id.startswith(evidence_id)
            or evidence_id.startswith(message_id)
            for evidence_id in valid_ids
        )

    valid_attachments = [
        attachment
        for attachment in result.captured_attachments
        if belongs_to_valid_evidence(attachment.message_id)
    ]
    valid_albums = [
        album for album in result.incomplete_albums
        if belongs_to_valid_evidence(album.message_id)
    ]
    stake_messages = [
        evidence.stake_text for evidence in valid_evidences if evidence.stake_text
    ]
    excluded = len(result.evidences) - len(valid_evidences)
    # Evidências isoladas não comprovam a quinzena inteira. Somente uma
    # varredura concluída pode liberar a revisão; isso impede que um recorte
    # começando, por exemplo, no dia 27 seja aceito para o período 16–31.
    period_found = result.start_date_found and result.period_scan_complete
    first_evidence_date = ""
    if valid_evidences:
        first_evidence_date = min(
            valid_evidences,
            key=lambda item: datetime.strptime(item.message_date, "%d/%m/%Y"),
        ).message_date
    message = result.message
    if excluded:
        message = (
            f"{message} " if message else ""
        ) + f"{excluded} evidência(s) fora do período foram descartadas."
    if period_found and first_evidence_date:
        configured_start = start_date.strftime("%d/%m/%Y")
        if first_evidence_date != configured_start:
            message = (
                f"Sem movimento em {configured_start}; primeira evidência "
                f"reconhecida em {first_evidence_date}."
            )
    return replace(
        result,
        start_date_found=period_found,
        start_date=start_date.strftime("%d/%m/%Y"),
        evidences=valid_evidences,
        captured_attachments=valid_attachments,
        incomplete_albums=valid_albums,
        stake_messages=stake_messages,
        message=message,
    )


def merge_period_results(
    primary: WhatsAppProbeResult,
    supplemental: list[WhatsAppProbeResult],
    start_date: date,
    end_date: date,
) -> WhatsAppProbeResult:
    """Consolidate proven evidence from repeated reads of one fortnight.

    WhatsApp navigation is not deterministic: one attempt may reach early
    dates while another captures later albums.  Repeated sessions are merged
    by stable message id and attachment hash.  Only the current (primary)
    session may prove that the full calendar interval was traversed.
    """
    sources = [
        restrict_result_to_period(item, start_date, end_date)
        for item in [primary, *supplemental]
    ]
    # A complete current traversal is the authority for which messages belong
    # to the period.  Older attempts are useful for recovering image bytes,
    # but some historical builds emitted gallery tiles as if they were extra
    # messages.  Unioning those stale inventories made a completed read look
    # incomplete again.  During a partial traversal we still merge inventories
    # so repeated attempts can progressively recover the period.
    evidence_sources = [sources[0]] if primary.period_scan_complete else sources
    evidence_by_id: dict[str, WhatsAppEvidence] = {}
    for source in evidence_sources:
        for evidence in source.evidences:
            current = evidence_by_id.get(evidence.message_id)
            current_richness = (
                current.image_count + len(current.pdf_names) +
                bool(current.stake_text) + bool(current.quantity_hint)
                if current else -1
            )
            candidate_richness = (
                evidence.image_count + len(evidence.pdf_names) +
                bool(evidence.stake_text) + bool(evidence.quantity_hint)
            )
            if current is None or candidate_richness > current_richness:
                evidence_by_id[evidence.message_id] = evidence

    authoritative_ids = set(evidence_by_id)
    # The same photo can be reported under both a message id and a synthetic
    # album id.  Its content hash is the identity; counting (message, hash)
    # duplicated real pieces in the review.
    attachment_by_key: dict[str, WhatsAppAttachment] = {}
    coverage_attachments: list[WhatsAppAttachment] = []
    for source in sources:
        for attachment in source.captured_attachments:
            if primary.period_scan_complete and not any(
                related_id == attachment.message_id or
                related_id.startswith(attachment.message_id) or
                attachment.message_id.startswith(related_id)
                for related_id in authoritative_ids
            ):
                continue
            key = attachment.sha256 or attachment.path
            if not Path(attachment.path).exists():
                continue
            coverage_attachments.append(attachment)
            existing = attachment_by_key.get(key)
            candidate_exact = attachment.message_id in authoritative_ids
            existing_exact = bool(
                existing and existing.message_id in authoritative_ids
            )
            if existing is None or (candidate_exact and not existing_exact):
                attachment_by_key[key] = attachment

    evidences = sorted(
        evidence_by_id.values(),
        key=lambda item: (
            datetime.strptime(item.message_date, "%d/%m/%Y"),
            item.message_time,
            item.message_id,
        ),
    )
    attachments = list(attachment_by_key.values())

    def related(message_id: str, evidence_id: str) -> bool:
        return (
            message_id == evidence_id or
            message_id.startswith(evidence_id) or
            evidence_id.startswith(message_id)
        )

    incomplete: list[WhatsAppAlbumStatus] = []
    for evidence in evidences:
        if evidence.image_count <= 0:
            continue
        captured = len({
            attachment.sha256 or attachment.path
            for attachment in coverage_attachments
            if related(attachment.message_id, evidence.message_id)
        })
        if captured < evidence.image_count:
            incomplete.append(WhatsAppAlbumStatus(
                message_id=evidence.message_id,
                expected=evidence.image_count,
                captured=captured,
            ))

    stakes = [item.stake_text for item in evidences if item.stake_text]
    period_complete = bool(primary.period_scan_complete)
    return replace(
        primary,
        connected=any(item.connected for item in sources),
        group_found=any(item.group_found for item in sources),
        start_date=start_date.strftime("%d/%m/%Y"),
        start_date_found=period_complete and bool(evidences),
        period_scan_complete=period_complete,
        visible_images=sum(item.image_count for item in evidences),
        visible_pdfs=sum(len(item.pdf_names) for item in evidences),
        ok_reactions=sum(bool(item.has_ok) for item in evidences),
        stake_messages=stakes,
        evidences=evidences,
        captured_attachments=attachments,
        incomplete_albums=incomplete,
    )


def _parse_probe_output(output: str) -> WhatsAppProbeResult:
    for line in reversed(output.splitlines()):
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("kind") == "result":
            return WhatsAppProbeResult.from_dict(data)
    raise RuntimeError("O leitor do WhatsApp não devolveu um resultado reconhecível.")


def probe_whatsapp(
    start_date: date,
    end_date: date,
    group_name: str = GROUP_NAME,
    timeout_seconds: int = 1500,
) -> WhatsAppProbeResult:
    if not NODE_EXECUTABLE.exists():
        raise RuntimeError("O componente de leitura do WhatsApp não foi localizado.")
    if not PROBE_SCRIPT.exists():
        raise RuntimeError("O arquivo do leitor do WhatsApp não foi localizado.")

    profile_dir = configuration_directory() / "whatsapp-browser"
    profile_dir.mkdir(parents=True, exist_ok=True)

    environment = os.environ.copy()
    environment["NODE_PATH"] = str(NODE_MODULES)
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    command = [
        str(NODE_EXECUTABLE),
        str(PROBE_SCRIPT),
        "--group",
        group_name,
        "--start",
        start_date.isoformat(),
        "--end",
        end_date.isoformat(),
        "--profile",
        str(profile_dir),
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=timeout_seconds,
            creationflags=creation_flags,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "O tempo de sincronização terminou. Mantenha o WhatsApp aberto no "
            "celular e tente continuar pela mesma sessão."
        ) from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        message = detail[-1] if detail else "Falha desconhecida ao abrir o WhatsApp."
        raise RuntimeError(message)

    return _parse_probe_output(completed.stdout)
