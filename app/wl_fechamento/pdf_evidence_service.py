from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path


BUNDLED_PDFTOPPM = Path(
    r"C:\Users\lilia\.cache\codex-runtimes\codex-primary-runtime"
    r"\dependencies\native\poppler\Library\bin\pdftoppm.exe"
)


def render_pdf_pages(source: Path, output_root: Path) -> list[Path]:
    """Render every PDF page for the same visual pipeline used by photos."""
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    target = output_root / f"pdf_{digest}"
    target.mkdir(parents=True, exist_ok=True)
    existing = sorted(target.glob("pagina-*.png"))
    if existing:
        return existing
    executable = shutil.which("pdftoppm") or (
        str(BUNDLED_PDFTOPPM) if BUNDLED_PDFTOPPM.exists() else ""
    )
    if not executable:
        raise RuntimeError("O renderizador local de PDF não foi localizado.")
    prefix = target / "pagina"
    completed = subprocess.run(
        [executable, "-png", "-r", "200", str(source), str(prefix)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            completed.stderr.strip() or "Não foi possível abrir o PDF recebido."
        )
    pages = sorted(target.glob("pagina-*.png"))
    if not pages:
        raise RuntimeError("O PDF não produziu nenhuma página legível.")
    return pages
