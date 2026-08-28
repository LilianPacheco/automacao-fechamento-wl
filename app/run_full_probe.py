from datetime import date

from wl_fechamento.chrome_bridge import probe_whatsapp_chrome


result = probe_whatsapp_chrome(
    date(2026, 7, 16),
    date(2026, 7, 31),
    timeout_seconds=900,
)
print(result, flush=True)
