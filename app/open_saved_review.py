from pathlib import Path

from wl_fechamento.app import FechamentoApp
from wl_fechamento.chrome_bridge import load_saved_whatsapp_session


SESSION_DIRECTORY = (
    Path(__file__).resolve().parent
    / "runtime_captures"
    / "sessao_definitiva_v141"
)


def main() -> None:
    app = FechamentoApp()
    app.last_whatsapp_result = load_saved_whatsapp_session(SESSION_DIRECTORY)
    app.after(600, app._start_photo_review)
    app.mainloop()


if __name__ == "__main__":
    main()
