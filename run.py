"""Entry point for the frozen executable.

Starts the uvicorn server, opens the default browser, and keeps the
process alive until the user closes the console window.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser


HOST = "127.0.0.1"
PORT = 8000


def _find_free_port(start: int = 8000, end: int = 8100) -> int:
    """Try ports from start to end, return the first free one."""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port in range {start}-{end}")


def _open_browser_later(url: str, delay: float = 1.5) -> None:
    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass
    threading.Thread(target=_open, daemon=True).start()


def main() -> int:
    port = _find_free_port(PORT)
    url = f"http://{HOST}:{port}"

    print()
    print("  File Organizer")
    print("  ──────────────────────────────────────")
    print(f"  Open: {url}")
    print("  Press Ctrl+C to stop.")
    print()

    # Import lazily so PyInstaller sees the module
    import uvicorn
    import app as app_module

    _open_browser_later(url)

    try:
        uvicorn.run(
            app_module.app,
            host=HOST,
            port=port,
            log_level="info",
            access_log=False,
        )
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())