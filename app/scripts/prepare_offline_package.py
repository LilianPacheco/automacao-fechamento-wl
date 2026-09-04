from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from wl_fechamento.chrome_bridge import load_latest_complete_whatsapp_session  # noqa: E402
from wl_fechamento.whatsapp_service import WhatsAppAttachment  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="Data inicial DD/MM/AAAA")
    parser.add_argument("--end", required=True, help="Data final DD/MM/AAAA")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    start = datetime.strptime(args.start, "%d/%m/%Y").date()
    end = datetime.strptime(args.end, "%d/%m/%Y").date()
    output = args.output.expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"A pasta de destino não está vazia: {output}")
    output.mkdir(parents=True, exist_ok=True)

    result = load_latest_complete_whatsapp_session(start, end)
    copied: list[WhatsAppAttachment] = []
    for index, attachment in enumerate(result.captured_attachments, start=1):
        source = Path(attachment.path)
        extension = source.suffix.lower() or ".jpg"
        safe_message_id = "".join(
            character if character.isalnum() or character in "-_" else "-"
            for character in attachment.message_id
        )
        destination = output / (
            f"{safe_message_id}_{attachment.sha256[:12]}_foto_{index:04d}{extension}"
        )
        shutil.copy2(source, destination)
        copied.append(WhatsAppAttachment(
            message_id=attachment.message_id,
            filename=destination.name,
            mime_type=attachment.mime_type,
            path=str(destination),
            size=destination.stat().st_size,
            sha256=attachment.sha256,
        ))
    packaged = replace(result, captured_attachments=copied)
    (output / "sessao_whatsapp.json").write_text(
        json.dumps(asdict(packaged), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(output)
    print(f"{len(copied)} foto(s) copiadas")


if __name__ == "__main__":
    main()
