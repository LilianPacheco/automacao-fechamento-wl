from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from PIL import Image


APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from wl_fechamento.chrome_bridge import load_saved_whatsapp_session
from wl_fechamento.label_parser import LabelDraft, parse_document_text
from wl_fechamento.ocr_service import _orange_label_crop, read_image_text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--full-rotations", action="store_true")
    parser.add_argument("--retry-low-confidence", action="store_true")
    parser.add_argument("--only-orange-label", action="store_true")
    args = parser.parse_args()
    root = args.directory.resolve()
    result = load_saved_whatsapp_session(root)
    images = [
        attachment for attachment in result.captured_attachments
        if attachment.mime_type.lower().startswith("image/")
    ]
    dates = {item.message_id: item.message_date for item in result.evidences}
    cache_path = root / "revisao_temporaria.json"
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(cache, dict):
            cache = {}
    except (OSError, json.JSONDecodeError):
        cache = {}

    def message_date(message_id: str) -> str:
        for candidate, value in dates.items():
            if message_id == candidate or message_id.startswith(candidate) or candidate.startswith(message_id):
                return value
        return ""

    def valid_cached(items: object) -> bool:
        if not isinstance(items, list) or not items:
            return False
        warnings = [
            str(warning).lower()
            for item in items if isinstance(item, dict)
            for warning in item.get("warnings", [])
        ]
        if any("ler a foto" in warning for warning in warnings):
            return False
        if args.retry_low_confidence and any("baixa confian" in warning for warning in warnings):
            return False
        return True

    pending = []
    for attachment in images:
        key = f"{attachment.message_id}:{attachment.sha256}"
        if not valid_cached(cache.get(key)):
            if args.only_orange_label:
                try:
                    with Image.open(attachment.path) as source:
                        if _orange_label_crop(source) is None:
                            continue
                except OSError:
                    continue
            pending.append((attachment, key))

    def process(item: tuple[object, str]) -> tuple[str, list[dict]]:
        attachment, key = item
        try:
            rotations = (0, 90, 180, 270) if args.full_rotations else (0,)
            reading = read_image_text(Path(attachment.path), rotations=rotations)
            drafts = parse_document_text(
                reading.text,
                message_id=attachment.message_id,
                message_date=message_date(attachment.message_id),
                source_path=attachment.path,
            )
            for draft in drafts:
                if reading.score < 35:
                    draft.warnings.append("Leitura da foto com baixa confiança")
                    draft.status = "CONFIRMAR"
            return key, [asdict(draft) for draft in drafts]
        except Exception as exc:
            failed = LabelDraft(
                message_id=attachment.message_id,
                message_date=message_date(attachment.message_id),
                source_path=attachment.path,
                status="CONFIRMAR",
                warnings=[f"Não foi possível ler a foto: {exc}"],
            )
            return key, [asdict(failed)]

    completed = len(images) - len(pending)
    print(json.dumps({"total": len(images), "cached": completed, "pending": len(pending)}), flush=True)
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 6))) as executor:
        futures = [executor.submit(process, item) for item in pending]
        for future in as_completed(futures):
            key, drafts = future.result()
            cache[key] = drafts
            completed += 1
            temporary = cache_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(cache_path)
            if completed % 5 == 0 or completed == len(images):
                print(json.dumps({"processed": completed, "total": len(images)}), flush=True)


if __name__ == "__main__":
    main()
