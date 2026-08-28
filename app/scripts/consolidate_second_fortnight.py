from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CAPTURES_ROOT = APP_ROOT / "runtime_captures"
OUTPUT = CAPTURES_ROOT / "quinzena_consolidada_2026-07_v180"
START_DATE = "16/07/2026"
VALID_DATES = {f"{day:02d}/07/2026" for day in range(16, 32)}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_group(value: str) -> str:
    return value.replace("Ã§", "ç").replace("Ã£", "ã")


def chrome_group(path: Path) -> tuple[str, str, str] | None:
    match = re.search(
        r"WhatsApp Image (\d{4})-(\d{2})-(\d{2}) at (\d{2})\.(\d{2})\.(\d{2})",
        path.name,
    )
    if not match:
        return None
    year, month, day, hour, minute, second = match.groups()
    date = f"{day}/{month}/{year}"
    if date not in VALID_DATES:
        return None
    total_minutes = int(hour) * 60 + int(minute)
    # The live gallery showed these exact WhatsApp message/album groups.
    if date == "21/07/2026":
        group_time = "18:36" if total_minutes < 19 * 60 else "19:50"
    elif date == "16/07/2026":
        group_time = "19:10" if total_minutes < 20 * 60 else "20:00"
    elif date == "22/07/2026":
        if total_minutes < 18 * 60:
            group_time = "15:10"
        elif total_minutes < 19 * 60:
            group_time = "18:50"
        elif total_minutes < 19 * 60 + 35:
            group_time = "19:26"
        elif total_minutes < 19 * 60 + 39:
            group_time = "19:37"
        elif total_minutes < 20 * 60:
            group_time = "19:40"
        else:
            group_time = "20:27"
    else:
        group_time = f"{hour}:{minute}"
    return date, group_time, f"chrome-{year}{month}{day}-{group_time.replace(':', '')}"


def main() -> None:
    payloads: list[tuple[Path, dict]] = []
    evidences: dict[str, dict] = {}
    hash_to_message: dict[str, str] = {}
    hash_to_all_messages: dict[str, set[str]] = defaultdict(set)
    candidate_files: set[Path] = set()

    for session_path in CAPTURES_ROOT.glob("*/sessao_whatsapp.json"):
        if session_path.parent == OUTPUT:
            continue
        try:
            payload = json.loads(session_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("start_date") != START_DATE:
            continue
        if "AWL x Expedi" not in normalize_group(str(payload.get("group_name", ""))):
            continue
        payloads.append((session_path.parent, payload))
        for item in payload.get("evidences", []):
            if not isinstance(item, dict) or item.get("message_date") not in VALID_DATES:
                continue
            message_id = str(item.get("message_id", ""))
            if not message_id:
                continue
            previous = evidences.get(message_id, {})
            merged = dict(previous)
            for key in ("message_id", "message_date", "message_time", "sender", "stake_text"):
                if item.get(key):
                    merged[key] = item[key]
            merged["image_count"] = max(int(previous.get("image_count", 0)), int(item.get("image_count", 0)))
            merged["pdf_names"] = sorted(set(previous.get("pdf_names", [])) | set(item.get("pdf_names", [])))
            merged["has_ok"] = bool(previous.get("has_ok") or item.get("has_ok"))
            evidences[message_id] = merged
        for attachment in payload.get("captured_attachments", []):
            if not isinstance(attachment, dict):
                continue
            digest = str(attachment.get("sha256", ""))
            message_id = str(attachment.get("message_id", ""))
            if digest and message_id:
                hash_to_message.setdefault(digest, message_id)
                hash_to_all_messages[digest].add(message_id)
        candidate_files.update(
            path for path in session_path.parent.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )

    # Some earlier extension versions represented a subset of a large album as
    # a second, smaller album. Shared hashes on the same date identify those
    # aliases safely; keep the larger album as the canonical message.
    alias_to_canonical: dict[str, str] = {}
    for message_ids in hash_to_all_messages.values():
        albums = [item for item in message_ids if item.startswith("album-") and item in evidences]
        if len(albums) < 2 or len({evidences[item].get("message_date") for item in albums}) != 1:
            continue
        canonical = max(albums, key=lambda item: int(evidences[item].get("image_count", 0)))
        for alias in albums:
            if alias != canonical:
                alias_to_canonical[alias] = canonical
    for alias, canonical in alias_to_canonical.items():
        alias_evidence = evidences.pop(alias, {})
        canonical_evidence = evidences[canonical]
        canonical_evidence["image_count"] = max(
            int(canonical_evidence.get("image_count", 0)),
            int(alias_evidence.get("image_count", 0)),
        )
        canonical_evidence["has_ok"] = bool(
            canonical_evidence.get("has_ok") or alias_evidence.get("has_ok")
        )
    hash_to_message = {
        digest: alias_to_canonical.get(message_id, message_id)
        for digest, message_id in hash_to_message.items()
    }

    # These folders contain successful captures without their own snapshot.
    for name in ("final_fortnight_v130", "quinzena_completa_v140"):
        directory = CAPTURES_ROOT / name
        if directory.exists():
            candidate_files.update(
                path for path in directory.iterdir()
                if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
            )

    chrome_files: dict[tuple[str, str, str], list[tuple[Path, str]]] = defaultdict(list)
    for directory in (
        CAPTURES_ROOT / "chrome_live_2026-07-16",
        CAPTURES_ROOT / "chrome_live_2026-07-21",
        CAPTURES_ROOT / "chrome_live_2026-07-22",
    ):
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            group = chrome_group(path)
            if group:
                chrome_files[group].append((path, sha256(path)))

    # Map each live Chrome album to the message id already known from matching
    # hashes. This assigns every newly recovered image to the correct album.
    chrome_assignment: dict[str, str] = {}
    for (date, time, fallback_id), files in chrome_files.items():
        known = [hash_to_message[digest] for _, digest in files if digest in hash_to_message]
        albums = [message_id for message_id in known if message_id.startswith("album-")]
        message_id = Counter(albums or known).most_common(1)[0][0] if (albums or known) else fallback_id
        for _, digest in files:
            chrome_assignment[digest] = message_id
        evidence = evidences.setdefault(message_id, {
            "message_id": message_id,
            "message_date": date,
            "message_time": time,
            "sender": "",
            "image_count": 0,
            "pdf_names": [],
            "stake_text": "",
            "has_ok": False,
        })
        evidence["image_count"] = max(int(evidence.get("image_count", 0)), len(files))
        evidence["message_date"] = date
        evidence["message_time"] = time
        candidate_files.update(path for path, _ in files)

    evidence_ids = sorted(evidences, key=len, reverse=True)
    records: dict[str, tuple[Path, str]] = {}
    for path in sorted(candidate_files):
        digest = sha256(path)
        message_id = chrome_assignment.get(digest) or hash_to_message.get(digest)
        if not message_id:
            message_id = next((item for item in evidence_ids if path.name.startswith(item + "_")), "")
        if not message_id:
            continue
        records.setdefault(digest, (path, message_id))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    # The folder is versioned and dedicated to this consolidation. Remove only
    # generated files from a prior interrupted run, never source captures.
    for path in OUTPUT.iterdir():
        if path.is_file() and (path.suffix.lower() in IMAGE_SUFFIXES or path.name in {
            "sessao_whatsapp.json", "revisao_temporaria.json", "revisao_temporaria.html", "manifesto_consolidacao.json"
        }):
            path.unlink()

    attachments: list[dict] = []
    counts: Counter[str] = Counter()
    for digest, (source, message_id) in sorted(records.items(), key=lambda item: (evidences.get(item[1][1], {}).get("message_date", ""), item[1][1], item[0])):
        counts[message_id] += 1
        target_name = f"{message_id}_{digest[:12]}_foto_{counts[message_id]:03d}.jpg"
        target = OUTPUT / target_name
        shutil.copy2(source, target)
        attachments.append({
            "message_id": message_id,
            "filename": target.name,
            "mime_type": "image/jpeg",
            "path": str(target),
            "size": target.stat().st_size,
            "sha256": digest,
        })

    incomplete = []
    zero_capture_aliases: set[str] = set()
    for message_id, evidence in evidences.items():
        if not message_id.startswith("album-") or counts[message_id] != 0:
            continue
        try:
            hour, minute = map(int, str(evidence.get("message_time", "")).split(":"))
        except ValueError:
            continue
        timestamp = hour * 60 + minute
        for other_id, other in evidences.items():
            if (
                other_id != message_id
                and other_id.startswith("album-")
                and counts[other_id] >= int(other.get("image_count", 0)) > 0
                and other.get("message_date") == evidence.get("message_date")
            ):
                try:
                    other_hour, other_minute = map(int, str(other.get("message_time", "")).split(":"))
                except ValueError:
                    continue
                if abs(timestamp - (other_hour * 60 + other_minute)) <= 10:
                    zero_capture_aliases.add(message_id)
                    break
    for message_id in zero_capture_aliases:
        evidences.pop(message_id, None)

    for message_id, evidence in evidences.items():
        captured = counts[message_id]
        expected = int(evidence.get("image_count", 0))
        if captured > expected:
            evidence["image_count"] = captured
            expected = captured
        if expected and captured < expected:
            incomplete.append({"message_id": message_id, "expected": expected, "captured": captured})

    ordered_evidence = sorted(
        evidences.values(),
        key=lambda item: (
            tuple(reversed(str(item.get("message_date", "")).split("/"))),
            str(item.get("message_time", "")),
            str(item.get("message_id", "")),
        ),
    )
    output_payload = {
        "connected": True,
        "group_found": True,
        "start_date_found": True,
        "start_date": START_DATE,
        "group_name": "AWL x Expedição Prellog",
        "visible_images": len(attachments),
        "visible_pdfs": sum(len(item.get("pdf_names", [])) for item in ordered_evidence),
        "ok_reactions": sum(bool(item.get("has_ok")) for item in ordered_evidence),
        "stake_messages": sorted({item.get("stake_text", "") for item in ordered_evidence if item.get("stake_text")}),
        "evidences": ordered_evidence,
        "captured_attachments": attachments,
        "incomplete_albums": incomplete,
        "message": "Consolidação local somente leitura; planilha oficial não alterada.",
    }
    (OUTPUT / "sessao_whatsapp.json").write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Reuse OCR results already computed in earlier successful sessions.
    merged_cache: dict[str, list[dict]] = {}
    for cache_path in CAPTURES_ROOT.glob("*/revisao_temporaria.json"):
        if cache_path.parent == OUTPUT:
            continue
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            merged_cache.update({str(key): value for key, value in data.items() if isinstance(value, list)})
    (OUTPUT / "revisao_temporaria.json").write_text(
        json.dumps(merged_cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = {
        "source_sessions": len(payloads),
        "candidate_files": len(candidate_files),
        "unique_images": len(attachments),
        "evidence_messages": len(ordered_evidence),
        "incomplete_albums": incomplete,
        "seeded_ocr_cache_entries": len(merged_cache),
    }
    (OUTPUT / "manifesto_consolidacao.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
