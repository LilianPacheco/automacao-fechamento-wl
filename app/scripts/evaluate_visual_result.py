from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from wl_fechamento.vision_service import VisionAnalysis, evaluate_against_reference  # noqa: E402


def load_analysis(path: Path) -> VisionAnalysis:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return VisionAnalysis.from_dict(payload)


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
        default=None,
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=APP_DIR / "runtime_captures" / "nova_analise_visual",
    )
    args = parser.parse_args()
    paths = [args.analysis] if args.analysis else sorted(args.directory.glob("analise_*.json"))
    results = []
    totals = {
        "fotos": 0,
        "confirmados_automaticamente": 0,
        "corretos": 0,
        "divergentes": 0,
        "pendentes": 0,
    }
    for analysis_path in paths:
        analysis = load_analysis(analysis_path)
        matched = find_historical_reference(analysis.source_path)
        if matched is None:
            continue
        review_path, reference = matched
        result = evaluate_against_reference(analysis, reference)
        result["analise"] = str(analysis_path)
        result["referencia_historica"] = str(review_path)
        results.append(result)
        totals["fotos"] += 1
        for key in (
            "confirmados_automaticamente", "corretos", "divergentes", "pendentes"
        ):
            totals[key] += int(result[key])
    automatic = totals["confirmados_automaticamente"]
    totals["precisao_automatica_percentual"] = (
        round(totals["corretos"] / automatic * 100, 1) if automatic else None
    )
    print(json.dumps({"resumo": totals, "resultados": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
