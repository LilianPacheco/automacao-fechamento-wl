from __future__ import annotations

import json
import base64
import hashlib
import re
import secrets
import subprocess
import threading
import uuid
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .whatsapp_service import GROUP_NAME, WhatsAppProbeResult, merge_period_results
from .config import configuration_directory


BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 8765
CHROME_EXECUTABLE = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
CHROME_PROFILE = "Profile 2"  # Nome visível no Chrome: AWL
EXTENSION_DIRECTORY = Path(__file__).resolve().parents[1] / "chrome_extension"


class _ReusableHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class ChromeBridge:
    def __init__(
        self,
        start_date: date,
        end_date: date,
        attachment_root: Path | None = None,
        target_test_date: date | None = None,
        target_album_size: int | None = None,
        target_album_message_id: str | None = None,
    ) -> None:
        self.session_id = uuid.uuid4().hex
        self.token = secrets.token_urlsafe(24)
        self.config = {
            "session_id": self.session_id,
            "token": self.token,
            "group_name": GROUP_NAME,
            "start_label": start_date.strftime("%d/%m/%Y"),
            "end_label": end_date.strftime("%d/%m/%Y"),
        }
        try:
            manifest = json.loads(
                (EXTENSION_DIRECTORY / "manifest.json").read_text(encoding="utf-8")
            )
            self.config["extension_version"] = str(manifest.get("version", ""))
        except (OSError, json.JSONDecodeError):
            self.config["extension_version"] = ""
        if target_test_date is not None and target_album_size is not None:
            self.config["target_test_date"] = target_test_date.strftime("%d/%m/%Y")
            self.config["target_album_size"] = max(1, int(target_album_size))
            if target_album_message_id:
                self.config["target_album_message_id"] = str(target_album_message_id)
        self.extension_seen = threading.Event()
        self.result_ready = threading.Event()
        self.latest_payload: dict[str, Any] | None = None
        self.attachment_directory = (
            attachment_root
            if attachment_root is not None
            else configuration_directory() / "Capturas" / self.session_id
        )
        self.attachments: list[dict[str, Any]] = []
        self.server: _ReusableHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def _save_session_snapshot(self) -> None:
        """Keep long WhatsApp reads recoverable if the app is closed afterwards."""
        if self.latest_payload is None:
            return
        snapshot = dict(self.latest_payload)
        snapshot["captured_attachments"] = list(self.attachments)
        try:
            self.attachment_directory.mkdir(parents=True, exist_ok=True)
            target = self.attachment_directory / "sessao_whatsapp.json"
            temporary = self.attachment_directory / "sessao_whatsapp.tmp"
            temporary.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(target)
        except OSError:
            # A falha ao salvar o resumo não pode interromper a captura das fotos.
            return

    def start(self) -> None:
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *_args: object) -> None:
                return

            def _cors(self) -> None:
                origin = self.headers.get("Origin", "")
                if origin.startswith("chrome-extension://"):
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")

            def _json_response(self, status: int, data: dict[str, Any]) -> None:
                encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self._cors()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def do_OPTIONS(self) -> None:  # noqa: N802
                self.send_response(204)
                self._cors()
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def do_GET(self) -> None:  # noqa: N802
                if self.path != "/config":
                    self._json_response(404, {"error": "not_found"})
                    return
                bridge.extension_seen.set()
                self._json_response(200, bridge.config)

            def do_POST(self) -> None:  # noqa: N802
                if self.path not in {"/result", "/attachment"}:
                    self._json_response(404, {"error": "not_found"})
                    return
                try:
                    limit = 18_000_000 if self.path == "/attachment" else 2_000_000
                    requested_length = int(self.headers.get("Content-Length", "0"))
                    if requested_length <= 0 or requested_length > limit:
                        self._json_response(413, {"error": "payload_too_large"})
                        return
                    length = requested_length
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                    self._json_response(400, {"error": "invalid_json"})
                    return
                if (
                    payload.get("session_id") != bridge.session_id
                    or payload.get("token") != bridge.token
                ):
                    self._json_response(403, {"error": "invalid_session"})
                    return
                if self.path == "/attachment":
                    try:
                        message_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(payload["message_id"]))[:160]
                        original_name = Path(str(payload.get("filename", "evidencia.bin"))).name
                        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", original_name)[:120]
                        encoded = str(payload["base64"])
                        content = base64.b64decode(encoded, validate=True)
                        if not message_id or not content or len(content) > 12_000_000:
                            raise ValueError("invalid attachment")
                    except (KeyError, ValueError, TypeError):
                        self._json_response(400, {"error": "invalid_attachment"})
                        return
                    digest = hashlib.sha256(content).hexdigest()
                    try:
                        bridge.attachment_directory.mkdir(parents=True, exist_ok=True)
                        target = bridge.attachment_directory / f"{message_id}_{digest[:12]}_{safe_name}"
                        target.write_bytes(content)
                    except OSError:
                        self._json_response(500, {"error": "attachment_storage_failed"})
                        return
                    metadata = {
                        "message_id": str(payload["message_id"]),
                        "filename": original_name,
                        "mime_type": str(payload.get("mime_type", "application/octet-stream")),
                        "path": str(target),
                        "size": len(content),
                        "sha256": digest,
                    }
                    duplicate = any(
                        item["message_id"] == metadata["message_id"]
                        and item["filename"] == metadata["filename"]
                        and item["sha256"] == metadata["sha256"]
                        for item in bridge.attachments
                    )
                    if not duplicate:
                        bridge.attachments.append(metadata)
                    bridge._save_session_snapshot()
                    self._json_response(200, {"ok": True, "sha256": digest, "size": len(content)})
                    return
                # Mais de um perfil do Chrome pode ter a extensão instalada.
                # Uma resposta final de um perfil sem o grupo correto não pode
                # encerrar a leitura que ainda está rodando no perfil AWL.
                current_has_group = bool(
                    bridge.latest_payload and bridge.latest_payload.get("group_found")
                )
                payload_has_group = bool(payload.get("group_found"))
                if payload_has_group or not current_has_group:
                    bridge.latest_payload = payload
                    bridge.latest_payload["captured_attachments"] = list(bridge.attachments)
                    bridge._save_session_snapshot()
                if payload.get("final") is True and payload_has_group:
                    bridge.result_ready.set()
                self._json_response(200, {"ok": True})

        try:
            self.server = _ReusableHTTPServer((BRIDGE_HOST, BRIDGE_PORT), Handler)
        except OSError as exc:
            raise RuntimeError(
                "A comunicação local do Chrome já está em uso. Feche outra "
                "execução do Fechamento WL e tente novamente."
            ) from exc
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    def wait_for_result(self, timeout_seconds: int) -> WhatsAppProbeResult:
        if not self.extension_seen.wait(timeout=50):
            raise RuntimeError(
                "A extensão do Fechamento WL não iniciou no Chrome. "
                "Será necessário habilitá-la uma vez."
            )
        if not self.result_ready.wait(timeout=timeout_seconds):
            if self.latest_payload is not None:
                payload = dict(self.latest_payload)
                payload["captured_attachments"] = list(self.attachments)
                self.latest_payload = payload
                self._save_session_snapshot()
                return WhatsAppProbeResult.from_dict(payload)
            raise RuntimeError(
                "O Chrome abriu, mas a leitura não terminou dentro do tempo esperado."
            )
        if self.latest_payload is None:
            raise RuntimeError("A extensão não devolveu o resultado da leitura.")
        return WhatsAppProbeResult.from_dict(self.latest_payload)


def load_saved_whatsapp_session(directory: Path) -> WhatsAppProbeResult:
    """Recover a saved read from its snapshot and locally captured image files."""
    snapshot_path = directory / "sessao_whatsapp.json"
    if not snapshot_path.exists():
        raise RuntimeError("O resumo da sessão do WhatsApp não foi localizado.")
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("O resumo salvo da sessão do WhatsApp está inválido.") from exc

    evidence_ids = sorted(
        {
            str(item.get("message_id", ""))
            for item in payload.get("evidences", [])
            if isinstance(item, dict) and item.get("message_id")
        },
        key=len,
        reverse=True,
    )
    attachments: list[dict[str, Any]] = []
    album_counts: dict[str, int] = {}
    for image_path in sorted(directory.iterdir()):
        if not image_path.is_file() or image_path.suffix.lower() not in {
            ".jpg", ".jpeg", ".png", ".webp"
        }:
            continue
        message_id = next(
            (candidate for candidate in evidence_ids if image_path.name.startswith(f"{candidate}_")),
            image_path.name.split("_", 1)[0],
        )
        content = image_path.read_bytes()
        attachments.append({
            "message_id": message_id,
            "filename": image_path.name,
            "mime_type": "image/jpeg",
            "path": str(image_path),
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
        if message_id.startswith("album-"):
            album_counts[message_id] = album_counts.get(message_id, 0) + 1

    incomplete_albums: list[dict[str, Any]] = []
    for message_id, captured in album_counts.items():
        expected_match = re.search(r"-(\d+)$", message_id)
        expected = int(expected_match.group(1)) if expected_match else captured
        if captured != expected:
            incomplete_albums.append({
                "message_id": message_id,
                "expected": expected,
                "captured": captured,
            })

    payload["captured_attachments"] = attachments
    payload["visible_images"] = max(int(payload.get("visible_images", 0)), len(attachments))
    payload["incomplete_albums"] = incomplete_albums
    return WhatsAppProbeResult.from_dict(payload)


def merge_saved_whatsapp_sessions(
    current: WhatsAppProbeResult,
    start_date: date,
    end_date: date,
) -> WhatsAppProbeResult:
    """Reuse verified local captures from earlier attempts of this period."""
    captures_root = configuration_directory() / "Capturas"
    start_label = start_date.strftime("%d/%m/%Y")
    supplemental: list[WhatsAppProbeResult] = []
    if captures_root.exists():
        snapshots = sorted(
            captures_root.glob("*/sessao_whatsapp.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for snapshot in snapshots:
            try:
                payload = json.loads(snapshot.read_text(encoding="utf-8"))
                if str(payload.get("start_date") or "") != start_label:
                    continue
                supplemental.append(load_saved_whatsapp_session(snapshot.parent))
            except (OSError, json.JSONDecodeError, RuntimeError):
                continue
    return merge_period_results(
        current, supplemental, start_date, end_date
    )


def load_latest_complete_whatsapp_session(
    start_date: date,
    end_date: date,
    captures_root: Path | None = None,
) -> WhatsAppProbeResult:
    """Open the newest completed local read for exactly this fortnight.

    This is the presentation-safe recovery path: it never substitutes another
    period and it still merges only locally saved image bytes belonging to the
    authoritative completed inventory.
    """
    root = captures_root or configuration_directory() / "Capturas"
    start_label = start_date.strftime("%d/%m/%Y")
    if not root.exists():
        raise RuntimeError("Nenhuma leitura salva foi encontrada neste computador.")
    snapshots = sorted(
        root.glob("*/sessao_whatsapp.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for snapshot in snapshots:
        try:
            payload = json.loads(snapshot.read_text(encoding="utf-8"))
            if str(payload.get("start_date") or "") != start_label:
                continue
            if not bool(payload.get("period_scan_complete")):
                continue
            current = load_saved_whatsapp_session(snapshot.parent)
            result = merge_saved_whatsapp_sessions(
                current, start_date, end_date
            ) if captures_root is None else merge_period_results(
                current,
                [
                    load_saved_whatsapp_session(item.parent)
                    for item in snapshots
                    if item.parent != snapshot.parent
                    and json.loads(item.read_text(encoding="utf-8")).get("start_date") == start_label
                ],
                start_date,
                end_date,
            )
            if result.period_scan_complete and result.captured_attachments:
                return result
        except (OSError, json.JSONDecodeError, RuntimeError):
            continue
    raise RuntimeError(
        "Ainda não existe uma leitura completa salva para a quinzena selecionada."
    )


def chrome_is_running() -> bool:
    completed = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    return '"chrome.exe"' in completed.stdout.lower()


def probe_whatsapp_chrome(
    start_date: date,
    end_date: date,
    timeout_seconds: int = 960,
) -> WhatsAppProbeResult:
    if not CHROME_EXECUTABLE.exists():
        raise RuntimeError("O Google Chrome não foi localizado.")
    if not (EXTENSION_DIRECTORY / "manifest.json").exists():
        raise RuntimeError("A extensão local do Fechamento WL não foi localizada.")
    bridge = ChromeBridge(start_date, end_date)
    bridge.start()
    try:
        current = bridge.wait_for_result(timeout_seconds)
        return merge_saved_whatsapp_sessions(current, start_date, end_date)
    finally:
        bridge.close()
