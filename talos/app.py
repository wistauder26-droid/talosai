"""Native Desktop-App: TalosAI in einem eigenen Fenster (ohne Browser).

Startet den FastAPI-Server auf einem freien localhost-Port in einem Thread und
öffnet ihn in einem nativen Fenster (pywebview). Auf dem Mac per Doppelklick
über das mit scripts/build-mac-app.sh erzeugte TalosAI.app.

Start: `talos-app`  (benötigt das Extra: `pip install '.[app]'`)
"""

from __future__ import annotations

import socket
import threading
import time


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    try:
        import webview
    except ImportError:
        raise SystemExit(
            "pywebview fehlt. Installiere die App-Abhängigkeit:\n"
            "  pip install 'talos-ai[app]'\n"
            "Alternativ läuft TalosAI im Browser mit: talos-web"
        )

    import uvicorn

    from .webapp import app

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    threading.Thread(target=server.run, daemon=True).start()

    # kurz warten, bis der Server erreichbar ist
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)

    webview.create_window(
        "TalosAI", f"http://127.0.0.1:{port}",
        width=1280, height=860, min_size=(900, 600),
    )
    webview.start()


if __name__ == "__main__":
    main()
