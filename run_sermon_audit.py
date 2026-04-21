#!/usr/bin/env python3
"""End-to-end sermon audit: YouTube URL → transcript → findings → HTML → PDF.

Given a YouTube URL plus preacher/church metadata, runs the full pipeline:
  1. yt-dlp downloads subtitles + extracts video metadata
  2. clean_vtt.py produces a cleaned timestamped transcript
  3. generate_findings.py calls claude -p to produce the findings JSON
  4. report_generator/generate_report.py produces the HTML
  5. to_pdf.py produces the PDF
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def sh(cmd: list[str], check: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess:
    print("$ " + " ".join(cmd), file=sys.stderr)
    return subprocess.run(cmd, check=check, text=True, cwd=cwd)


def yt_dump_json(url: str) -> dict:
    r = subprocess.run(
        ["yt-dlp", "--skip-download", "--dump-json", url],
        capture_output=True, text=True, check=True,
    )
    return json.loads(r.stdout)


def yt_download_subs(url: str, out_template: str) -> None:
    sh([
        "yt-dlp", "--skip-download",
        "--write-auto-sub", "--write-sub",
        "--sub-lang", "en", "--sub-format", "vtt",
        "--output", out_template, url,
    ])


def slugify(s: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return s[:maxlen].rstrip("_")


def find_vtt(stem_prefix: str) -> Path:
    """Find the VTT file yt-dlp just wrote matching the template prefix."""
    tdir = ROOT / "transcripts"
    candidates = sorted(tdir.glob(f"{stem_prefix}*.vtt"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"No VTT found for prefix {stem_prefix}")
    return candidates[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="YouTube URL")
    ap.add_argument("--preacher", required=True)
    ap.add_argument("--church", required=True)
    ap.add_argument("--church-location", default="")
    ap.add_argument("--series", default="")
    ap.add_argument("--preaching-text", default="")
    ap.add_argument("--skip-pdf", action="store_true")
    args = ap.parse_args()

    print(f"\n=== {args.preacher} — {args.church} ===", file=sys.stderr)

    # 1. Get video metadata
    meta = yt_dump_json(args.url)
    yt_id = meta["id"]
    title = meta["title"].strip()
    upload_date = meta["upload_date"]  # YYYYMMDD
    upload_date_iso = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    duration = int(meta.get("duration", 0))

    # 2. Download VTT captions
    prefix = f"{upload_date}_{yt_id}"
    template = str(ROOT / "transcripts" / f"{prefix}_%(title)s.%(ext)s")
    yt_download_subs(args.url, template)
    vtt_path = find_vtt(prefix)

    # 3. Clean VTT → timestamped text
    preacher_slug = slugify(args.preacher)
    title_slug = slugify(title, maxlen=40)
    txt_path = ROOT / "transcripts" / f"{upload_date}_{preacher_slug}_{title_slug}.txt"
    sh([
        "python3", str(ROOT / "clean_vtt.py"),
        str(vtt_path), "-o", str(txt_path),
    ])

    # 4. Generate findings JSON via claude -p
    findings_path = ROOT / "findings" / f"{upload_date}_{preacher_slug}_{title_slug}.json"
    gen_cmd = [
        "python3", str(ROOT / "generate_findings.py"),
        "--transcript", str(txt_path),
        "--youtube-id", yt_id,
        "--preacher", args.preacher,
        "--church", args.church,
        "--church-location", args.church_location,
        "--sermon-title", title,
        "--upload-date", upload_date_iso,
        "--runtime-seconds", str(duration),
        "--series", args.series,
        "--preaching-text", args.preaching_text,
        "--output", str(findings_path),
    ]
    sh(gen_cmd)

    # 5. Generate HTML report
    html_path = ROOT / "reports" / f"{upload_date}_{preacher_slug}_{title_slug}.html"
    sh([
        "python3", str(ROOT / "report_generator" / "generate_report.py"),
        str(findings_path), str(html_path),
    ])

    # 6. Generate PDF
    if not args.skip_pdf:
        sh(["python3", str(ROOT / "to_pdf.py"), str(html_path)])

    print(f"\nDone: {html_path.name}", file=sys.stderr)
    print(f"  http://localhost:8765/{html_path.name}", file=sys.stderr)


if __name__ == "__main__":
    main()
