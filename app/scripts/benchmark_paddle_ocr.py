from __future__ import annotations

import json
import sys
from pathlib import Path

VENDOR = Path(r"C:\WLAppRuntime\vendor_ocr")
sys.path.insert(0, str(VENDOR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from paddleocr import PaddleOCR  # noqa: E402


image_path = Path(sys.argv[1])
ocr = PaddleOCR(
    lang="pt",
    use_doc_orientation_classify=True,
    use_doc_unwarping=True,
    use_textline_orientation=True,
)
results = ocr.predict(input=str(image_path))
for result in results:
    payload = result.json
    if callable(payload):
        payload = payload()
    print(json.dumps(payload, ensure_ascii=False))
