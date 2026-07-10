import argparse
import threading
import time
import webbrowser

import uvicorn

from app.main import app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the DnD Notes application.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the application in the default browser.",
    )
    return parser.parse_args()


def open_browser_when_ready(server: uvicorn.Server, url: str) -> None:
    while not getattr(server, "started", False):
        if server.should_exit:
            return
        time.sleep(0.1)

    webbrowser.open(url)


def main() -> None:
    args = parse_args()
    browser_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    url = f"http://{browser_host}:{args.port}"

    config = uvicorn.Config(
        app,
        host=args.host,
        port=args.port,
        loop="asyncio",
        http="h11",
        lifespan="on",
        log_level="info",
    )
    server = uvicorn.Server(config)

    if not args.no_browser:
        threading.Thread(
            target=open_browser_when_ready,
            args=(server, url),
            daemon=True,
        ).start()

    print(f"DnD Notes is available at {url}")
    print("Press Ctrl+C to stop the server.")
    server.run()


if __name__ == "__main__":
    main()
