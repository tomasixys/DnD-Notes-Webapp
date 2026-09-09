import argparse
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from app.config import (
    ConfigurationError,
    apply_server_overrides,
    load_runtime_settings,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the DnD Notes application.")
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to a DnD Notes TOML configuration file.",
    )
    parser.add_argument(
        "--host",
        help="Override server.host from the configuration file.",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Override server.port from the configuration file.",
    )
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
    settings = load_runtime_settings(args.config)
    settings = apply_server_overrides(
        settings,
        host=args.host,
        port=args.port,
        open_browser=False if args.no_browser else None,
    )

    # Import after configuration validation so invalid startup never creates
    # application storage or constructs the FastAPI application.
    from app.application import create_app

    app = create_app(settings)
    host = settings.server.host
    port = settings.server.port
    browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    internal_url = f"http://{browser_host}:{port}"
    url = settings.server.public_origin or internal_url

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        loop="asyncio",
        http="h11",
        lifespan="on",
        log_level="info",
        proxy_headers=settings.server.proxy_headers,
        forwarded_allow_ips=",".join(
            settings.server.trusted_proxies
        ),
    )
    server = uvicorn.Server(config)

    if settings.server.open_browser:
        threading.Thread(
            target=open_browser_when_ready,
            args=(server, url),
            daemon=True,
        ).start()

    print(f"DnD Notes is available at {url}")
    print("Press Ctrl+C to stop the server.")
    try:
        server.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    try:
        main()
    except ConfigurationError as error:
        raise SystemExit(f"Configuration error: {error}") from error
