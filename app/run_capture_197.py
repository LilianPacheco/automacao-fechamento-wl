from datetime import date
from pathlib import Path

from wl_fechamento.chrome_bridge import ChromeBridge


root = Path(__file__).resolve().parent
output = root / "runtime_captures" / "quinzena_2026-07_recaptura_v200"
status = output / "captura_status.txt"
output.mkdir(parents=True, exist_ok=True)
status.write_text("CAPTURA_INICIADA\n", encoding="utf-8")
bridge = ChromeBridge(date(2026, 7, 16), date(2026, 7, 31), attachment_root=output)
bridge.start()
try:
    result = bridge.wait_for_result(960)
    status.write_text(
        "CAPTURA_FINAL\n"
        f"grupo={result.group_found}\n"
        f"data_inicial={result.start_date_found}\n"
        f"evidencias={len(result.evidences)}\n"
        f"anexos={len(result.captured_attachments)}\n"
        f"mensagem={result.message}\n",
        encoding="utf-8",
    )
finally:
    bridge.close()
