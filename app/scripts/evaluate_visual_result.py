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
    FieldCandidate,
    FieldDecision,
    VisionAnalysis,
    VisionReading,
    evaluate_against_reference,
)


def load_analysis(path: Path) -> VisionAnalysis:
    payload = json.loads(path.read_text(encoding="utf-8"))
    fields = {
        name: FieldDecision(
            **{
                **value,
                "candidates": [
                    FieldCandidate(**candidate)
                    for candidate in value.get("candidates", [])
                ],
            }
        )
        for name, value in payload["fields"].items()
    }
    return VisionAnalysis(
        source_path=payload["source_path"],
        label_crop_path=payload["label_crop_path"],
        fields=fields,
        readings=[VisionReading(**reading) for reading in payload["readings"]],
        product_type=payload.get("product_type", ""),
    )


def find_historical_reference(source_path: str) -> tuple[Path, dict] | None:
    captures = Path(os.environ["APPDATA"]) / "WL Fechamento" / "Capturas"
    reviews = sorted(
        captures.glob("*/revisao_temporaria.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    target = str(Path(source_path)).lower()
    for review_path in reviews:
        loaded = json.loads(review_path.read_text(encoding="utf-8"))
        groups = loaded.values() if isinstance(loaded, dict) else [loaded]
        for group in groups:
            for row in group if isinstance(group, list) else [group]:
                if not isinstance(row, dict):
                    continue
                if str(Path(str(row.get("source_path") or ""))).lower() == target:
                    return review_path, row
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--analysis",
        type=Path,
        default=APP_DIR / "runtime_captures" / "nova_analise_visual" / "analise_001.json",
    )
    args = parser.parse_args()
    analysis = load_analysis(args.analysis)
    matched = find_historical_reference(analysis.source_path)
    if matched is None:
        raise SystemExit("A foto não possui uma referência histórica correspondente.")
    review_path, reference = matched
    result = evaluate_against_reference(analysis, reference)
    result["analise"] = str(args.analysis)
    result["referencia_historica"] = str(review_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

