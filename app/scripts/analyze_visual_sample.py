from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from wl_fechamento.vision_service import (  # noqa: E402
    VisionAnalysis,
    analyze_image,
    apply_group_context,
)


def latest_review_images() -> list[Path]:
    captures = Path(os.environ["APPDATA"]) / "WL Fechamento" / "Capturas"
    reviews = sorted(
        captures.glob("*/revisao_temporaria.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not reviews:
        return []
    loaded = json.loads(reviews[0].read_text(encoding="utf-8"))
    rows = [item for group in loaded.values() for item in group if isinstance(item, dict)]
    unique: dict[str, Path] = {}
    for row in rows:
        source = Path(str(row.get("source_path") or ""))
        if source.is_file():
            unique.setdefault(str(source), source)
    return list(unique.values())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument(
        "--output",
        type=Path,
        default=APP_DIR / "runtime_captures" / "nova_analise_visual",
    )
    args = parser.parse_args()
    images = [args.path] if args.path else latest_review_images()
    images = [path for path in images if path and path.is_file()][: max(1, args.limit)]
    if not images:
        raise SystemExit("Nenhuma foto de revisão foi encontrada.")
    args.output.mkdir(parents=True, exist_ok=True)
    processed = []
    for index, image_path in enumerate(images, start=1):
        result_path = args.output / f"analise_{index:03d}.json"
        reused = False
        if result_path.exists():
            try:
                previous = json.loads(result_path.read_text(encoding="utf-8"))
                reused = str(previous.get("source_path") or "") == str(image_path)
            except (OSError, json.JSONDecodeError):
                reused = False
        if reused:
            analysis = VisionAnalysis.from_dict(previous)
        else:
            analysis = analyze_image(image_path, args.output / "evidencias")
            # Persist each expensive OCR result immediately. A large batch can
            # then resume safely after a shutdown or an interrupted run.
            analysis.save(result_path)
            print(json.dumps({
                "foto": str(image_path),
                "resultado": str(result_path),
                "etapa": "leitura_concluida_e_salva",
            }, ensure_ascii=False), flush=True)
        processed.append((image_path, result_path, analysis, reused))
    apply_group_context([item[2] for item in processed])
    summaries = []
    for image_path, result_path, analysis, reused in processed:
        analysis.save(result_path)
        summary = {
            "foto": str(image_path),
            "resultado": str(result_path),
            "reutilizado": reused,
            "campos_pendentes": analysis.pending_fields,
            "campos_confirmados": [
                name for name, field in analysis.fields.items()
                if field.status == "CONFIRMADO_AUTOMATICAMENTE"
            ],
        }
        summaries.append(summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    (args.output / "resumo.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
