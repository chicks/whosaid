#!/usr/bin/env python3
"""Convert a generated HTML report to PDF using headless Chrome.

Chrome renders the report using the print media stylesheet, so the YouTube
iframe is replaced with a plain video-URL line and flagged transcript
paragraphs get print-friendly borders.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_chrome() -> str:
    for path in CHROME_CANDIDATES:
        if Path(path).is_file():
            return path
    for cmd in ("google-chrome", "chromium", "chrome"):
        found = shutil.which(cmd)
        if found:
            return found
    sys.exit(
        "Could not find Chrome/Chromium. Install Google Chrome, or pass --chrome-path."
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html", type=Path, help="Path to HTML report")
    ap.add_argument("pdf", type=Path, nargs="?", default=None,
                    help="Output PDF path (default: same name, .pdf extension)")
    ap.add_argument("--chrome-path", default=None)
    args = ap.parse_args()

    html_path = args.html.resolve()
    if not html_path.is_file():
        sys.exit(f"HTML file not found: {html_path}")

    pdf_path = args.pdf or html_path.with_suffix(".pdf")
    pdf_path = pdf_path.resolve()

    chrome = args.chrome_path or find_chrome()

    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=5000",
        f"--print-to-pdf={pdf_path}",
        f"file://{html_path}",
    ]
    print(f"Rendering {html_path.name} → {pdf_path.name} …", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not pdf_path.is_file():
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        sys.exit(f"Chrome exited {result.returncode}; PDF not written.")

    size_kb = pdf_path.stat().st_size / 1024
    print(f"Wrote {pdf_path} ({size_kb:.1f} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
