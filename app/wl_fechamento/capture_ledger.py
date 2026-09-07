from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any


class CaptureLedger:
    """Durable, append-safe record of WhatsApp inventory and downloads."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    message_date TEXT NOT NULL DEFAULT '',
                    message_time TEXT NOT NULL DEFAULT '',
                    sender TEXT NOT NULL DEFAULT '',
                    message_text TEXT NOT NULL DEFAULT '',
                    expected_images INTEGER NOT NULL DEFAULT 0,
                    pdf_names_json TEXT NOT NULL DEFAULT '[]',
                    stake_text TEXT NOT NULL DEFAULT '',
                    quantity_hint REAL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS attachments (
                    message_id TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    path TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    saved_at TEXT NOT NULL,
                    PRIMARY KEY (message_id, content_sha256, filename)
                );
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    saved_at TEXT NOT NULL,
                    is_final INTEGER NOT NULL,
                    period_scan_complete INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def record_payload(self, payload: dict[str, Any]) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        evidences = payload.get("evidences", [])
        with closing(self._connect()) as connection, connection:
            for item in evidences if isinstance(evidences, list) else []:
                if not isinstance(item, dict) or not item.get("message_id"):
                    continue
                connection.execute("""
                    INSERT INTO messages (
                        message_id, message_date, message_time, sender,
                        message_text, expected_images, pdf_names_json,
                        stake_text, quantity_hint, first_seen_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(message_id) DO UPDATE SET
                        message_date=excluded.message_date,
                        message_time=excluded.message_time,
                        sender=excluded.sender,
                        message_text=CASE
                            WHEN length(excluded.message_text) > length(messages.message_text)
                            THEN excluded.message_text ELSE messages.message_text END,
                        expected_images=max(messages.expected_images, excluded.expected_images),
                        pdf_names_json=excluded.pdf_names_json,
                        stake_text=CASE
                            WHEN excluded.stake_text <> '' THEN excluded.stake_text
                            ELSE messages.stake_text END,
                        quantity_hint=coalesce(excluded.quantity_hint, messages.quantity_hint),
                        last_seen_at=excluded.last_seen_at
                """, (
                    str(item.get("message_id", "")),
                    str(item.get("message_date", "")),
                    str(item.get("message_time", "")),
                    str(item.get("sender", "")),
                    str(item.get("message_text", "")),
                    max(0, int(item.get("image_count", 0) or 0)),
                    json.dumps(item.get("pdf_names", []), ensure_ascii=False),
                    str(item.get("stake_text", "")),
                    item.get("quantity_hint"), now, now,
                ))
            connection.execute(
                "INSERT INTO checkpoints (saved_at, is_final, period_scan_complete, payload_json) "
                "VALUES (?, ?, ?, ?)",
                (
                    now, int(bool(payload.get("final"))),
                    int(bool(payload.get("period_scan_complete"))),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )

    def record_attachment(self, metadata: dict[str, Any]) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("""
                INSERT OR IGNORE INTO attachments (
                    message_id, content_sha256, filename, mime_type,
                    path, size, saved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(metadata["message_id"]), str(metadata["sha256"]),
                str(metadata["filename"]), str(metadata["mime_type"]),
                str(metadata["path"]), int(metadata["size"]),
                datetime.now().isoformat(timespec="seconds"),
            ))

    def coverage(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection, connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("""
                SELECT m.message_id, m.message_date, m.expected_images,
                       count(a.content_sha256) AS captured_images
                  FROM messages m
             LEFT JOIN attachments a ON a.message_id = m.message_id
              GROUP BY m.message_id, m.message_date, m.expected_images
              ORDER BY m.message_date, m.message_id
            """).fetchall()
        return [dict(row) for row in rows]
