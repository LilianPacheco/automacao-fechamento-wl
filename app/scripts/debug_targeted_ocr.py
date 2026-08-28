from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from wl_fechamento.label_parser import parse_document_text  # noqa: E402
from wl_fechamento.ocr_service import (  # noqa: E402
    _orange_label_crop,
    _prepare_paddle_label,
    _prepare_variant,
    _read_layout_assisted,
    _rectify_label,
)
from wl_fechamento.paddle_ocr_service import read_text as read_paddle_text  # noqa: E402


def describe(text: str) -> dict:
    return {
        "text": text,
        "drafts": [
            {
                "work": draft.work,
                "product": draft.product,
                "piece": draft.piece,
                "section": draft.section,
                "length": draft.length,
                "unit_volume": draft.unit_volume,
                "warnings": draft.warnings,
            }
            for draft in parse_document_text(text)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--images-only", action="store_true")
    args = parser.parse_args()
    with Image.open(args.image) as source, tempfile.TemporaryDirectory(prefix="wl_debug_") as temporary:
        temporary_path = Path(temporary)
        label = _orange_label_crop(source)
        if label is not None:
            label.save(temporary_path / "orange_crop.png")
            _prepare_paddle_label(label).save(temporary_path / "paddle_label.png")
            rectified = _rectify_label(label)
            if rectified.height > rectified.width:
                rectified = rectified.rotate(90, expand=True)
            rectified.save(temporary_path / "rectified.png")
            _prepare_variant(rectified, 0).save(temporary_path / "layout_prepared.png")
        if args.images_only:
            layout_text, layout_confidence = "", 0.0
        else:
            layout_text, layout_confidence = _read_layout_assisted(source, temporary_path)
        full_text = ""
        full_confidence = 0.0
        if label is not None and not args.images_only:
            label_path = temporary_path / "label.png"
            _prepare_paddle_label(label).save(label_path, format="PNG", optimize=True)
            full_text, full_confidence = read_paddle_text(label_path, quality="medium")
        payload = {
            "image": str(args.image),
            "layout_confidence": layout_confidence,
            "full_confidence": full_confidence,
            "layout": describe(layout_text),
            "full": describe(full_text),
            "merged": describe("\n".join(part for part in (layout_text, full_text) if part)),
        }
        if args.output:
            artifact_dir = args.output.with_suffix("")
            if artifact_dir.exists():
                shutil.rmtree(artifact_dir)
            shutil.copytree(temporary_path, artifact_dir)
            payload["artifacts"] = str(artifact_dir)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    else:
        print(rendered)


if __name__ == "__main__":
    main()
