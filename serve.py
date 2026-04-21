#!/usr/bin/env python3
"""Serve the reports/ directory over HTTP on localhost.

Needed because browsers treat file:// URLs as unique security origins,
which breaks YouTube's embedded player (Error 153).
"""
import argparse
import http.server
import socketserver
from pathlib import Path

DEFAULT_PORT = 8765


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument(
        "--directory",
        type=Path,
        default=Path(__file__).parent / "reports",
    )
    args = ap.parse_args()

    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(
        *a, directory=str(args.directory), **kw
    )
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"Serving {args.directory} at http://localhost:{args.port}/")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
