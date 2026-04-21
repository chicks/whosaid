#!/usr/bin/env python3
"""Convert a YouTube auto-caption VTT file into a clean, readable transcript.

Input VTT has rolling duplicate lines and per-word timing tags. This script
strips the inline tags, dedupes the rolling lines, and emits a plain-text
transcript with a timestamp marker every N seconds (default 30) for citation.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

INLINE_TAG_RE = re.compile(r"<[^>]+>")
TS_RE = re.compile(r"^(\d\d):(\d\d):(\d\d)\.\d+\s-->\s")


def parse_vtt(vtt_text: str):
    cues = []
    current_start = None
    for line in vtt_text.splitlines():
        m = TS_RE.match(line)
        if m:
            h, mm, s = (int(x) for x in m.groups())
            current_start = h * 3600 + mm * 60 + s
            continue
        if current_start is None:
            continue
        if not line.strip():
            current_start = None
            continue
        if line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        clean = INLINE_TAG_RE.sub("", line).strip()
        if clean:
            cues.append((current_start, clean))
    return cues


def stamp(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"[{h:02d}:{m:02d}:{s:02d}]"


def build_transcript(cues, marker_every: int = 30) -> str:
    out_lines: list[str] = []
    last_text = None
    next_marker = 0
    buf: list[str] = []

    def flush(at_seconds: int):
        nonlocal buf
        if buf:
            out_lines.append(f"{stamp(at_seconds)} " + " ".join(buf))
            buf = []

    for sec, text in cues:
        if text == last_text:
            continue
        last_text = text
        while sec >= next_marker + marker_every and buf:
            flush(next_marker)
            next_marker += marker_every
        if sec >= next_marker:
            next_marker = (sec // marker_every) * marker_every
        buf.append(text)
    flush(next_marker)
    return "\n".join(out_lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vtt", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=None)
    ap.add_argument("--marker-every", type=int, default=30,
                    help="Seconds between timestamp markers in output")
    args = ap.parse_args()

    text = args.vtt.read_text(encoding="utf-8")
    cues = parse_vtt(text)
    transcript = build_transcript(cues, marker_every=args.marker_every)

    if args.output:
        args.output.write_text(transcript, encoding="utf-8")
        print(f"Wrote {args.output} ({len(transcript):,} chars, {len(cues):,} cues)",
              file=sys.stderr)
    else:
        sys.stdout.write(transcript)


if __name__ == "__main__":
    main()
