from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import date
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
        return cls(
            message_id=str(data.get("message_id", "")),
            message_date=str(data.get("message_date", "")),
            message_time=str(data.get("message_time", "")),
            sender=str(data.get("sender", "")),
            image_count=max(0, int(data.get("image_count", 0))),
            pdf_names=[str(item) for item in data.get("pdf_names", [])],
            stake_text=str(data.get("stake_text", "")),
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
