#!/usr/bin/env python3
"""Generate a self-contained HTML audit report from a findings JSON + transcript.

Usage: python3 generate_report.py path/to/findings.json path/to/output.html
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SEV_ORDER = {"severe": 3, "moderate": 2, "low": 1, "none": 0}
TS_RE = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\]\s?(.*)")


def parse_timestamp_to_seconds(ts: str) -> int:
    """Parse 'HH:MM:SS' to seconds."""
    h, m, s = (int(p) for p in ts.split(":"))
    return h * 3600 + m * 60 + s


def seconds_to_display(total: int) -> str:
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_transcript(path: Path) -> list[dict]:
    """Return list of {seconds, timestamp, text}."""
    paragraphs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = TS_RE.match(line.strip())
        if not m:
            continue
        h, mm, ss, text = m.groups()
        seconds = int(h) * 3600 + int(mm) * 60 + int(ss)
        paragraphs.append({
            "seconds": seconds,
            "timestamp": f"{h}:{mm}:{ss}",
            "text": text.strip(),
        })
    return paragraphs


def yt_deeplink(video_id: str, seconds: int) -> str:
    return f"https://www.youtube.com/watch?v={video_id}&t={seconds}s"


def highest_severity(sevs: list[str]) -> str:
    if not sevs:
        return "none"
    return max(sevs, key=lambda s: SEV_ORDER.get(s, 0))


def assign_paragraph_severities(paragraphs: list[dict], findings: list[dict]) -> None:
    """Mutate paragraphs to add 'flagged_severity' and 'flagged_finding_ids'."""
    for p in paragraphs:
        p["flagged_severity"] = "none"
        p["flagged_finding_ids"] = []

    for f in findings:
        start = f.get("timestamp_seconds")
        if start is None:
            continue
        end = f.get("timestamp_end_seconds", start + 30)
        sev = f.get("severity", "low")
        for p in paragraphs:
            p_start = p["seconds"]
            p_end = p_start + 30
            if p_end > start and p_start < end + 1:
                p["flagged_finding_ids"].append(f["id"])
                current = p["flagged_severity"]
                if SEV_ORDER.get(sev, 0) > SEV_ORDER.get(current, 0):
                    p["flagged_severity"] = sev


CSS = r"""
* { box-sizing: border-box; }
:root {
  --c-bg: #fafaf7;
  --c-fg: #1d1d1b;
  --c-muted: #6b6b67;
  --c-border: #d8d6cf;
  --c-card: #ffffff;
  --c-severe: #9b1c1c;
  --c-severe-bg: #fde8e8;
  --c-moderate: #c2410c;
  --c-moderate-bg: #ffedd5;
  --c-low: #a16207;
  --c-low-bg: #fef3c7;
  --c-affirm: #166534;
  --c-affirm-bg: #dcfce7;
  --c-pastor: #7c2d12;
  --c-jesus: #1e3a8a;
  --c-link: #1e40af;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  background: var(--c-bg);
  color: var(--c-fg);
  max-width: 1000px;
  margin: 0 auto;
  padding: 2rem 1.5rem 5rem;
  line-height: 1.55;
}
h1 { font-size: 2rem; margin: 0 0 .25rem; letter-spacing: -0.01em; }
h2 { font-size: 1.4rem; margin: 2.5rem 0 .75rem; border-bottom: 1px solid var(--c-border); padding-bottom: .3rem; }
h3 { font-size: 1.1rem; margin: 0 0 .25rem; }
h4 { font-size: .85rem; text-transform: uppercase; letter-spacing: 0.08em; margin: .25rem 0; color: var(--c-muted); }
a { color: var(--c-link); text-decoration: none; border-bottom: 1px solid rgba(30,64,175,0.3); }
a:hover { border-bottom-color: var(--c-link); }
blockquote { margin: 0; padding: 0; font-style: normal; }
code { font-family: 'SF Mono', Menlo, monospace; font-size: 0.85em; background: #f0efe9; padding: 1px 4px; border-radius: 3px; }

/* Header */
.meta-line { color: var(--c-muted); font-size: 0.95rem; margin: 0 0 1rem; }
.meta-line span + span::before { content: "·"; margin: 0 .5rem; }
.yt-embed { aspect-ratio: 16 / 9; width: 100%; margin: 1rem 0 0; border: 1px solid var(--c-border); }
.yt-embed iframe { width: 100%; height: 100%; border: 0; }

/* Scorecard */
.scorecard { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem; }
.axis-card {
  background: var(--c-card);
  border: 1px solid var(--c-border);
  border-radius: 6px;
  padding: 1rem;
}
.axis-card .axis-label { font-size: .8rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--c-muted); }
.axis-card .axis-verdict { font-size: 1.3rem; font-weight: 600; margin: .3rem 0 .5rem; }
.axis-card p { margin: 0; font-size: 0.95rem; }

/* Severity badges */
.sev-badge {
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 2px 8px;
  border-radius: 3px;
  color: white;
}
.sev-severe { background: var(--c-severe); }
.sev-moderate { background: var(--c-moderate); }
.sev-low { background: var(--c-low); }

.axis-card.axis-severity-severe { border-left: 4px solid var(--c-severe); }
.axis-card.axis-severity-moderate { border-left: 4px solid var(--c-moderate); }
.axis-card.axis-severity-low { border-left: 4px solid var(--c-low); }

/* Timeline */
.timeline-wrap { margin: 1rem 0 .25rem; }
.timeline-track {
  position: relative;
  height: 36px;
  background: #ebe9e1;
  border-radius: 18px;
  border: 1px solid var(--c-border);
}
.timeline-marker {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  text-decoration: none;
  border-bottom: 2px solid white;
}
.timeline-marker:hover { transform: translate(-50%, -50%) scale(1.3); z-index: 2; }
.timeline-marker-severe { background: var(--c-severe); }
.timeline-marker-moderate { background: var(--c-moderate); }
.timeline-marker-low { background: var(--c-low); }
.timeline-labels { display: flex; justify-content: space-between; color: var(--c-muted); font-size: .8rem; margin-top: .25rem; font-variant-numeric: tabular-nums; }

/* Findings */
.finding {
  background: var(--c-card);
  border: 1px solid var(--c-border);
  border-radius: 6px;
  padding: 1rem 1.25rem;
  margin-bottom: 1rem;
  border-left-width: 4px;
  border-left-style: solid;
}
.finding.sev-border-severe { border-left-color: var(--c-severe); }
.finding.sev-border-moderate { border-left-color: var(--c-moderate); }
.finding.sev-border-low { border-left-color: var(--c-low); }
.finding.headline { box-shadow: 0 2px 10px rgba(155,28,28,0.15); }

.finding-header { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; margin-bottom: .75rem; }
.finding-header h3 { flex: 1 1 100%; margin: .25rem 0 0; }
.finding-header .axis-tag {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--c-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  background: #ebe9e1;
  padding: 2px 8px;
  border-radius: 3px;
}
.finding-header .timestamp-link {
  font-size: 0.85rem;
  font-family: 'SF Mono', Menlo, monospace;
}
.finding-header .headline-tag {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--c-severe);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  background: var(--c-severe-bg);
  padding: 2px 8px;
  border-radius: 3px;
}

.contrast {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin: .5rem 0;
}
.contrast-3 {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: .75rem;
  margin: .5rem 0;
}
@media (max-width: 900px) { .contrast-3 { grid-template-columns: 1fr; } }
@media (max-width: 700px) { .contrast { grid-template-columns: 1fr; } }
.contrast-side { border-radius: 4px; padding: .75rem .9rem; }
.contrast-side.pastor { background: #fef7f4; border: 1px solid #f3d6c5; }
.contrast-side.jesus { background: #f4f6fe; border: 1px solid #c8d0ef; }
.contrast-side.wider-bible { background: #f4fef7; border: 1px solid #c5e4c8; }
.contrast-side.wider-bible blockquote strong { display: block; font-size: .8rem; color: #166534; margin-bottom: .2rem; letter-spacing: 0.03em; }
.contrast-side h4 { margin-top: 0; }
.contrast-side blockquote { font-size: 0.95rem; }
.contrast-side blockquote + blockquote { margin-top: .75rem; padding-top: .75rem; border-top: 1px dashed var(--c-border); }
.contrast-side.jesus blockquote strong { display: block; font-size: .8rem; color: var(--c-jesus); margin-bottom: .2rem; letter-spacing: 0.03em; }
.contrast-side blockquote p { margin: 0; }

.why-flagged {
  margin-bottom: .75rem;
  padding: .75rem .9rem;
  background: #faf7ea;
  border-left: 3px solid var(--c-low);
  border-radius: 0 4px 4px 0;
  font-size: 0.93rem;
}
.why-flagged strong { color: var(--c-low); }

.severity-context {
  margin-top: .75rem;
  font-size: 0.9rem;
  background: #fdf4f4;
  border-radius: 4px;
  padding: .5rem .9rem;
  border: 1px solid #f3d6d6;
}
.severity-context h4 { color: var(--c-severe); margin-top: 0; }
.severity-context ul { margin: 0; padding-left: 1.2rem; }
.severity-context li { margin-bottom: .2rem; }

.jump-link {
  display: inline-block;
  font-size: 0.85rem;
  margin-top: .4rem;
}

/* Affirmed / counter-signals */
.list-affirm {
  background: var(--c-affirm-bg);
  border: 1px solid #a7d7a7;
  border-radius: 6px;
  padding: .75rem 1rem .75rem 2rem;
  margin: .5rem 0 1rem;
}
.list-affirm li { margin: .15rem 0; }

/* CN markers table */
table.cn-markers { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
table.cn-markers th, table.cn-markers td { text-align: left; padding: .4rem .6rem; border-bottom: 1px solid var(--c-border); vertical-align: top; }
table.cn-markers th { background: #ebe9e1; font-weight: 600; font-size: .8rem; text-transform: uppercase; letter-spacing: 0.05em; }
.status-present { color: var(--c-severe); font-weight: 600; }
.status-low, .status-moderate { color: var(--c-moderate); font-weight: 500; }
.status-none { color: var(--c-muted); }

/* Transcript */
.transcript-note { color: var(--c-muted); font-size: 0.9rem; margin: 0 0 1rem; }
.transcript-para {
  margin: .4rem 0;
  padding: .35rem .7rem;
  border-radius: 4px;
  font-size: 0.95rem;
  line-height: 1.55;
}
.transcript-para.flagged-severe { background: var(--c-severe-bg); border-left: 3px solid var(--c-severe); }
.transcript-para.flagged-moderate { background: var(--c-moderate-bg); border-left: 3px solid var(--c-moderate); }
.transcript-para.flagged-low { background: var(--c-low-bg); border-left: 3px solid var(--c-low); }
.transcript-para .ts-link {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 0.8rem;
  margin-right: .5rem;
  color: var(--c-muted);
  border-bottom: 0;
  background: rgba(0,0,0,0.04);
  padding: 1px 6px;
  border-radius: 3px;
}
.transcript-para .ts-link:hover { background: rgba(30,64,175,0.1); color: var(--c-link); }
.transcript-para .finding-refs { font-size: 0.75rem; color: var(--c-muted); margin-left: .5rem; }
.transcript-para .finding-refs a { color: var(--c-muted); }

/* Fact-check cards */
.fact-check {
  background: var(--c-card);
  border: 1px solid var(--c-border);
  border-radius: 6px;
  padding: 1rem 1.25rem;
  margin-bottom: 1rem;
  border-left-width: 4px;
  border-left-style: solid;
}
.fact-check.verdict-supported { border-left-color: #166534; }
.fact-check.verdict-partial { border-left-color: #c2410c; }
.fact-check.verdict-contested { border-left-color: #a16207; }
.fact-check.verdict-misleading { border-left-color: #c2410c; }
.fact-check.verdict-unsupported { border-left-color: #6b6b67; }
.fact-check.verdict-false { border-left-color: var(--c-severe); }

.verdict-badge {
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 2px 8px;
  border-radius: 3px;
  color: white;
}
.verdict-badge.verdict-supported { background: #166534; }
.verdict-badge.verdict-partial { background: #c2410c; }
.verdict-badge.verdict-contested { background: #a16207; }
.verdict-badge.verdict-misleading { background: #c2410c; }
.verdict-badge.verdict-unsupported { background: #6b6b67; }
.verdict-badge.verdict-false { background: var(--c-severe); }

.fact-check-header { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; margin-bottom: .75rem; }
.fact-check-header h3 { flex: 1 1 100%; margin: .25rem 0 0; font-size: 1.05rem; font-weight: 500; }
.fact-check-block {
  margin: .75rem 0;
  padding: .75rem .9rem;
  border-radius: 4px;
  font-size: 0.93rem;
}
.fact-check-block h4 { margin: 0 0 .3rem; }
.fact-check-block.claim { background: #fef7f4; border: 1px solid #f3d6c5; }
.fact-check-block.evidence-cited { background: #faf7ea; border: 1px solid #ead994; }
.fact-check-block.analysis { background: #f4f6fe; border: 1px solid #c8d0ef; }
.fact-check-block p { margin: 0; }
.fact-check-block blockquote { margin: 0; font-size: 0.95rem; }
.fact-check-sources { font-size: 0.85rem; margin: .75rem 0 0; padding: .6rem .9rem; background: #f5f4ee; border-radius: 4px; }
.fact-check-sources h4 { margin: 0 0 .3rem; }
.fact-check-sources ul { margin: 0; padding-left: 1.2rem; }
.fact-check-sources li { margin: .2rem 0; line-height: 1.4; }
.fact-check-sources a { word-break: break-word; }

/* Print */
.print-only { display: none; }
@media print {
  body { max-width: none; margin: 0; padding: 0.5in; font-size: 10pt; background: white; color: black; }
  h1 { font-size: 18pt; }
  h2 { font-size: 13pt; page-break-after: avoid; break-after: avoid-page; margin-top: 1.2em; }
  h3 { font-size: 11pt; page-break-after: avoid; break-after: avoid-page; }
  .yt-embed { display: none !important; }
  .print-only { display: block; }
  .print-only.video-link { margin: .5rem 0 1rem; padding: .5rem .75rem; border: 1px solid #999; border-radius: 3px; font-size: 9pt; }
  .print-only.video-link a { color: black; word-break: break-all; }
  a { color: black; text-decoration: underline; border-bottom: 0; }
  .finding, .fact-check, .axis-card { page-break-inside: avoid; break-inside: avoid; box-shadow: none !important; }
  .sev-badge, .verdict-badge, .axis-tag, .headline-tag { color: black !important; background: #eee !important; border: 1px solid #999; }
  .contrast-side, .why-flagged, .severity-context, .fact-check-block, .fact-check-sources, .axis-card { background: #fff !important; border: 1px solid #bbb !important; }
  .transcript-para.flagged-severe, .transcript-para.flagged-moderate, .transcript-para.flagged-low {
    background: #fff !important;
    border-left: 2px solid #333 !important;
    page-break-inside: avoid;
    break-inside: avoid;
  }
  .timeline-track { border: 1px solid #bbb; background: #fff; }
  .timeline-marker { background: #333 !important; border-color: #333 !important; }
  #transcript { page-break-before: always; break-before: page; }
  .ts-link, .finding-refs, .jump-link { color: #666 !important; }
  iframe { display: none !important; }
  footer { page-break-before: auto; font-size: 8pt; }
}

/* Footer */
footer {
  margin-top: 4rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--c-border);
  color: var(--c-muted);
  font-size: 0.85rem;
}
footer h3 { font-size: 0.95rem; color: var(--c-fg); margin-bottom: .3rem; }
footer p { margin: .3rem 0; }
"""


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def render_jesus_quotes(quotes: list[dict]) -> str:
    parts = []
    for q in quotes:
        parts.append(
            f'<blockquote><strong>{esc(q["citation"])}</strong>'
            f'<p>{esc(q["text"])}</p></blockquote>'
        )
    return "\n".join(parts)


def render_severity_context(ctx: dict | None) -> str:
    if not ctx:
        return ""
    labels = {
        "reach": "Reach",
        "specificity": "Specificity",
        "reductionism": "Reductionism",
        "provenance": "Provenance",
        "speaker_signal": "Speaker's own signal",
    }
    items = "".join(
        f"<li><strong>{labels.get(k, k.replace('_', ' ').title())}:</strong> {esc(v)}</li>"
        for k, v in ctx.items()
    )
    return (
        '<div class="severity-context">'
        "<h4>Severity weighting</h4>"
        f"<ul>{items}</ul>"
        "</div>"
    )


def render_finding(f: dict, yt_id: str, transcript_by_sec: dict) -> str:
    sev = f.get("severity", "low")
    axis = f.get("axis", 1)
    ts_seconds = f.get("timestamp_seconds")
    ts_display = f.get("timestamp_display", "")
    headline_tag = '<span class="headline-tag">Headline</span>' if f.get("headline") else ""

    if ts_seconds is not None:
        ts_link = (
            f'<a href="{yt_deeplink(yt_id, ts_seconds)}" target="_blank" rel="noopener"'
            f' class="timestamp-link">▶ {esc(ts_display)}</a>'
        )
        # Jump to nearest transcript paragraph
        nearest = max((s for s in transcript_by_sec if s <= ts_seconds), default=None)
        jump = (
            f'<a href="#t-{nearest}" class="jump-link">Jump to transcript ↓</a>'
            if nearest is not None else ""
        )
    else:
        ts_link = f'<span class="timestamp-link" style="color: var(--c-muted);">{esc(ts_display)}</span>'
        jump = ""

    pastor_block = (
        '<div class="contrast-side pastor">'
        "<h4>Pastor</h4>"
        f"<blockquote><p>{esc(f['pastor_quote'])}</p></blockquote>"
        f"{jump}"
        "</div>"
    )
    jesus_block = (
        '<div class="contrast-side jesus">'
        "<h4>Jesus</h4>"
        f"{render_jesus_quotes(f['jesus_quotes'])}"
        "</div>"
    )

    return (
        f'<article id="{esc(f["id"])}" class="finding sev-border-{sev}{" headline" if f.get("headline") else ""}">'
        '<div class="finding-header">'
        f'<span class="sev-badge sev-{sev}">{sev}</span>'
        f'<span class="axis-tag">Axis {axis}</span>'
        f"{ts_link}"
        f"{headline_tag}"
        f'<h3>{esc(f["title"])}</h3>'
        "</div>"
        '<div class="why-flagged">'
        f'<strong>Why flagged:</strong> {esc(f["why_flagged"])}'
        "</div>"
        '<div class="contrast">'
        f"{pastor_block}"
        f"{jesus_block}"
        "</div>"
        f"{render_severity_context(f.get('severity_context'))}"
        "</article>"
    )


def render_bible_quotes(quotes: list[dict]) -> str:
    parts = []
    for q in quotes:
        parts.append(
            f'<blockquote><strong>{esc(q["citation"])}</strong>'
            f'<p>{esc(q["text"])}</p></blockquote>'
        )
    return "\n".join(parts)


def render_axis4_finding(f: dict, yt_id: str, transcript_by_sec: dict) -> str:
    sev = f.get("severity", "low")
    ts_seconds = f.get("timestamp_seconds")
    ts_display = f.get("timestamp_display", "")
    headline_tag = '<span class="headline-tag">Headline</span>' if f.get("headline") else ""

    if ts_seconds is not None:
        ts_link = (
            f'<a href="{yt_deeplink(yt_id, ts_seconds)}" target="_blank" rel="noopener"'
            f' class="timestamp-link">▶ {esc(ts_display)}</a>'
        )
        nearest = max((s for s in transcript_by_sec if s <= ts_seconds), default=None)
        jump = (
            f'<a href="#t-{nearest}" class="jump-link">Jump to transcript ↓</a>'
            if nearest is not None else ""
        )
    else:
        ts_link = f'<span class="timestamp-link" style="color: var(--c-muted);">{esc(ts_display)}</span>'
        jump = ""

    pastor_block = (
        '<div class="contrast-side pastor">'
        "<h4>Pastor</h4>"
        f"<blockquote><p>{esc(f['pastor_quote'])}</p></blockquote>"
        f"{jump}"
        "</div>"
    )
    jesus_block = (
        '<div class="contrast-side jesus">'
        "<h4>Jesus (Gospels)</h4>"
        f"{render_bible_quotes(f.get('jesus_passages', []))}"
        "</div>"
    )
    wider_block = (
        '<div class="contrast-side wider-bible">'
        "<h4>Wider Bible (OT &amp; NT non-Gospel)</h4>"
        f"{render_bible_quotes(f.get('wider_bible_passages', []))}"
        "</div>"
    )

    topic_line = (
        f'<div style="font-size:.8rem; color: var(--c-muted); '
        f'text-transform: uppercase; letter-spacing:.06em; margin:.25rem 0 .5rem;">'
        f'Topic: {esc(f["topic"])}</div>' if f.get("topic") else ""
    )

    analysis_block = ""
    if f.get("analysis"):
        analysis_block = (
            '<div class="fact-check-block analysis" style="margin-bottom:.75rem;">'
            "<h4>Canonical analysis</h4>"
            f'<p>{esc(f["analysis"])}</p>'
            "</div>"
        )

    return (
        f'<article id="{esc(f["id"])}" class="finding sev-border-{sev}{" headline" if f.get("headline") else ""}">'
        '<div class="finding-header">'
        f'<span class="sev-badge sev-{sev}">{sev}</span>'
        '<span class="axis-tag">Axis 4</span>'
        f"{ts_link}"
        f"{headline_tag}"
        f'<h3>{esc(f["title"])}</h3>'
        "</div>"
        f"{topic_line}"
        '<div class="why-flagged">'
        f'<strong>Why flagged:</strong> {esc(f["why_flagged"])}'
        "</div>"
        f"{analysis_block}"
        '<div class="contrast-3">'
        f"{pastor_block}"
        f"{jesus_block}"
        f"{wider_block}"
        "</div>"
        "</article>"
    )


VERDICT_CLASS = {
    "supported": "supported",
    "partially supported": "partial",
    "partially supported / overstated": "partial",
    "contested": "contested",
    "misleading": "misleading",
    "unsupported": "unsupported",
    "false": "false",
}


def render_fact_check(fc: dict, yt_id: str, transcript_by_sec: dict) -> str:
    verdict = fc.get("verdict", "unsupported").lower()
    vclass = VERDICT_CLASS.get(verdict, "unsupported")
    ts = fc.get("timestamp_seconds")
    ts_display = fc.get("timestamp_display", "")
    if ts is not None:
        ts_link = (
            f'<a href="{yt_deeplink(yt_id, ts)}" target="_blank" rel="noopener" '
            f'class="timestamp-link">▶ {esc(ts_display)}</a>'
        )
    else:
        ts_link = f'<span class="timestamp-link" style="color: var(--c-muted);">{esc(ts_display)}</span>'

    truncated_claim = fc["claim"]
    if len(truncated_claim) > 120:
        truncated_claim = truncated_claim[:117].rstrip() + "…"

    source_items = []
    for s in fc.get("sources", []):
        title = s.get("title") or s.get("url") or "(untitled source)"
        url = s.get("url")
        if url:
            source_items.append(f'<li><a href="{esc(url)}" target="_blank" rel="noopener">{esc(title)}</a></li>')
        else:
            source_items.append(f"<li>{esc(title)}</li>")
    sources_html = "".join(source_items)
    sources_block = (
        '<div class="fact-check-sources">'
        "<h4>Sources consulted</h4>"
        f"<ul>{sources_html}</ul>"
        "</div>"
        if sources_html else ""
    )

    return (
        f'<article id="{esc(fc["id"])}" class="fact-check verdict-{vclass}">'
        '<div class="fact-check-header">'
        f'<span class="verdict-badge verdict-{vclass}">{esc(fc["verdict"])}</span>'
        f"{ts_link}"
        f'<h3>“{esc(truncated_claim)}”</h3>'
        "</div>"
        '<div class="fact-check-block claim">'
        "<h4>Pastor's claim (full)</h4>"
        f'<blockquote>{esc(fc["claim"])}</blockquote>'
        "</div>"
        '<div class="fact-check-block evidence-cited">'
        "<h4>Evidence the pastor cited</h4>"
        f'<p>{esc(fc.get("evidence_cited_by_pastor", "None."))}</p>'
        "</div>"
        '<div class="fact-check-block analysis">'
        "<h4>What the evidence shows</h4>"
        f'<p>{esc(fc["analysis"])}</p>'
        "</div>"
        f"{sources_block}"
        "</article>"
    )


def render_timeline(findings: list[dict], runtime: int) -> str:
    markers = []
    for f in findings:
        ts = f.get("timestamp_seconds")
        if ts is None:
            continue
        pct = (ts / runtime) * 100
        sev = f.get("severity", "low")
        title = f'{f["title"]} @ {f.get("timestamp_display", "")}'
        markers.append(
            f'<a href="#{esc(f["id"])}" class="timeline-marker timeline-marker-{sev}" '
            f'style="left: {pct:.2f}%" title="{esc(title)}"></a>'
        )
    return (
        '<div class="timeline-wrap">'
        f'<div class="timeline-track">{"".join(markers)}</div>'
        '<div class="timeline-labels">'
        "<span>00:00:00</span>"
        f"<span>{seconds_to_display(runtime)}</span>"
        "</div>"
        "</div>"
    )


def render_axis_card(axis: dict) -> str:
    sev = axis.get("severity", "low")
    return (
        f'<div class="axis-card axis-severity-{sev}">'
        f'<div class="axis-label">{esc(axis["label"])}</div>'
        f'<div class="axis-verdict">{esc(axis["verdict"])}</div>'
        f'<p>{esc(axis["headline"])}</p>'
        "</div>"
    )


def render_cn_markers(markers: list[dict]) -> str:
    rows = []
    for m in markers:
        status = m["status"]
        status_class = "status-none"
        if status.lower().startswith(("present", "moderate", "high")):
            status_class = "status-present"
        elif "low" in status.lower() or "–low" in status.lower():
            status_class = "status-low"
        ref = m.get("reference", "")
        note = m.get("note", "")
        if ref and note:
            detail = f"{esc(note)} ({esc(ref)})"
        elif ref:
            detail = esc(ref)
        elif note:
            detail = esc(note)
        else:
            detail = ""
        rows.append(
            f'<tr><td>{esc(m["marker"])}</td>'
            f'<td class="{status_class}">{esc(status)}</td>'
            f'<td>{detail}</td></tr>'
        )
    return (
        '<table class="cn-markers">'
        "<thead><tr><th>Marker</th><th>Status</th><th>Notes</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def render_transcript(paragraphs: list[dict], yt_id: str, findings: list[dict]) -> str:
    findings_by_id = {f["id"]: f for f in findings}
    parts = []
    for p in paragraphs:
        sev = p.get("flagged_severity", "none")
        cls = "transcript-para"
        if sev != "none":
            cls += f" flagged-{sev}"
        ref_html = ""
        if p["flagged_finding_ids"]:
            refs = [
                f'<a href="#{fid}">{esc(findings_by_id[fid]["title"])}</a>'
                for fid in p["flagged_finding_ids"] if fid in findings_by_id
            ]
            ref_html = f'<span class="finding-refs">→ {"; ".join(refs)}</span>'
        link = (
            f'<a href="{yt_deeplink(yt_id, p["seconds"])}" target="_blank" '
            f'rel="noopener" class="ts-link">[{esc(p["timestamp"])}]</a>'
        )
        parts.append(
            f'<p id="t-{p["seconds"]}" class="{cls}">{link}{esc(p["text"])}{ref_html}</p>'
        )
    return "\n".join(parts)


def build_html(data: dict, paragraphs: list[dict]) -> str:
    meta = data["meta"]
    yt = meta["youtube_id"]
    runtime = meta["runtime_seconds"]
    findings = data["findings"]
    axis4_early = data.get("axis4_findings", [])
    transcript_by_sec = {p["seconds"]: p for p in paragraphs}
    assign_paragraph_severities(paragraphs, findings + axis4_early)

    findings_sorted = sorted(
        findings,
        key=lambda f: (
            -SEV_ORDER.get(f.get("severity", "low"), 0),
            0 if f.get("headline") else 1,
            f.get("axis", 1),
            f.get("timestamp_seconds") or 0,
        ),
    )

    title = f"Sermon Audit — {meta['preacher']} — {meta['sermon_title']}"
    header_meta = " ".join(
        f"<span>{esc(v)}</span>"
        for v in [
            meta["preacher"],
            meta["church"],
            meta.get("series", ""),
            meta["upload_date"],
            seconds_to_display(runtime),
        ]
        if v
    )

    scorecard_cards = [
        render_axis_card(data["scorecard"]["axis_1"]),
        render_axis_card(data["scorecard"]["axis_2"]),
    ]
    for key in ("axis_3", "axis_4"):
        if key in data.get("scorecard", {}):
            scorecard_cards.append(render_axis_card(data["scorecard"][key]))
    scorecard_html = '<div class="scorecard">' + "".join(scorecard_cards) + "</div>"

    axis4 = axis4_early
    # Timeline includes both axis 1/2 findings and axis 4 findings
    timeline_findings = findings + axis4
    timeline_html = render_timeline(timeline_findings, runtime)

    findings_html = "\n".join(
        render_finding(f, yt, transcript_by_sec) for f in findings_sorted
    )
    fact_checks = data.get("factual_claims", [])
    fact_checks_html = "\n".join(
        render_fact_check(fc, yt, transcript_by_sec) for fc in fact_checks
    )
    axis4_sorted = sorted(
        axis4,
        key=lambda f: (
            -SEV_ORDER.get(f.get("severity", "low"), 0),
            0 if f.get("headline") else 1,
            f.get("timestamp_seconds") or 9_999_999,
        ),
    )
    axis4_html = "\n".join(
        render_axis4_finding(f, yt, transcript_by_sec) for f in axis4_sorted
    )
    transcript_html = render_transcript(paragraphs, yt, timeline_findings)

    affirmed_html = ""
    if data.get("tenets_affirmed"):
        items = "".join(f"<li>{esc(t)}</li>" for t in data["tenets_affirmed"])
        affirmed_html = f'<ul class="list-affirm">{items}</ul>'

    counter_html = ""
    if data.get("counter_signals"):
        items = "".join(f"<li>{esc(t)}</li>" for t in data["counter_signals"])
        counter_html = f'<ul class="list-affirm">{items}</ul>'

    cn_html = render_cn_markers(data.get("cn_markers", []))

    other_axis2 = ""
    if data.get("other_axis2_rubrics"):
        rows = []
        for r in data["other_axis2_rubrics"]:
            note = f" — <span style='color: var(--c-muted);'>{esc(r['note'])}</span>" if r.get("note") else ""
            rows.append(f"<li><strong>{esc(r['rubric'])}:</strong> {esc(r['status'])}{note}</li>")
        other_axis2 = f"<ul>{''.join(rows)}</ul>"

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <div style="font-size:.75rem; color: var(--c-muted); letter-spacing:.1em; text-transform: uppercase;">Sermon Audit</div>
  <h1>{esc(meta['sermon_title'])}</h1>
  <p class="meta-line">{header_meta}</p>
  <p class="meta-line" style="margin-top:-.5rem"><em>Preaching text:</em> {esc(meta.get('preaching_text',''))} · <em>Gospel translation:</em> {esc(meta.get('gospel_translation','ESV'))}</p>
  {("<div class='yt-embed'>"
    f"<iframe src='https://www.youtube-nocookie.com/embed/{esc(yt)}' allowfullscreen"
    " allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture'"
    " referrerpolicy='strict-origin-when-cross-origin'></iframe></div>"
    "<div class='print-only video-link'>"
    f"Video: <a href='https://www.youtube.com/watch?v={esc(yt)}'>https://www.youtube.com/watch?v={esc(yt)}</a>"
    "</div>"
   ) if len(yt) == 11 and all(c.isalnum() or c in '-_' for c in yt)
   else f"<div class='yt-embed' style='aspect-ratio:auto;padding:1rem;background:#ebe9e1;'><em>Source: non-video (timestamps are estimated based on paragraph pacing). Original transcript: <code>{esc(meta.get('transcript_path',''))}</code></em></div>"}
</header>

<h2>Scorecard</h2>
{scorecard_html}

<h2>Summary</h2>
<p>{esc(data.get('summary', ''))}</p>

<h2>Timeline</h2>
<p class="transcript-note">Each marker = a flagged finding. Click to jump to the finding; hover for the title. Color indicates severity.</p>
{timeline_html}

<h2>Findings ({len(findings)})</h2>
{findings_html}

<h2>Whole-Bible Engagement ({len(axis4)})</h2>
<p class="transcript-note">For each major framing in the sermon, the pastor's claim is placed side-by-side with <strong>what Jesus said in the Gospels</strong> and <strong>what the wider Bible says</strong> (OT + NT non-Gospel). Surfaces cherry-picking, omitted counter-voices, and places where the canon itself contains tension the pastor did not acknowledge.</p>
{axis4_html or '<p>(none)</p>'}

<h2>Factual Claims &amp; Evidence Check ({len(fact_checks)})</h2>
<p class="transcript-note">Empirical claims the pastor made during the sermon, with a verdict on whether independent evidence supports them. Verdict scale: Supported · Partially supported · Contested · Misleading · Unsupported · False. “Evidence the pastor cited” records whether any source was named in the sermon itself.</p>
{fact_checks_html or '<p>(none extracted)</p>'}

<h2>Tenets affirmed</h2>
{affirmed_html or '<p>(none)</p>'}

<h2>Counter-signals</h2>
{counter_html or '<p>(none)</p>'}

<h2>Christian Nationalism marker rubric (Whitehead/Perry, Du Mez, Alberta)</h2>
{cn_html}

<h2>Other Axis-2 sub-rubrics</h2>
{other_axis2 or '<p>(none applicable to this sermon)</p>'}

<h2>Full transcript</h2>
<p class="transcript-note">Highlighted paragraphs contain flagged content (color = severity). Click any timestamp to jump to that moment on YouTube.</p>
{transcript_html}

<footer>
<h3>Methodology</h3>
<p><strong>Axis 1 — Fidelity to Jesus's Teachings:</strong> findings flag contradictions with, tensions against, or notable absences from Jesus's direct words in the four Gospels. Reference translation: {esc(meta.get('gospel_translation','ESV'))}.</p>
<p><strong>Axis 2 — Identifiable Biases / Harmful Rhetoric:</strong> co-equal sub-rubrics for Christian nationalism (Whitehead &amp; Perry's <em>Taking America Back for God</em>; Du Mez, <em>Jesus and John Wayne</em>; Alberta, <em>The Kingdom, the Power, and the Glory</em>), anti-Muslim framing, anti-LGBTQ framing, misogynistic framing, and anti-Jewish framing. Findings weighted by <em>reach × specificity × real-world harm potential</em>.</p>
<p><strong>Axis 3 — Factual Claims &amp; Evidence Check:</strong> empirical claims extracted from the sermon are compared against independent scholarly, journalistic, and primary sources. Each claim receives a verdict (Supported · Partially supported · Contested · Misleading · Unsupported · False) and records whether the pastor cited evidence when making the claim (a rhetorical concern distinct from the empirical verdict). No verdict is rendered without a cited source.</p>
<p><strong>Axis 4 — Whole-Bible Engagement:</strong> for each major framing in the sermon, the pastor's claim is placed side-by-side with Jesus's Gospel witness and with the wider biblical canon (OT and non-Gospel NT). This surfaces cherry-picking (citing a favorable verse while ignoring hostile ones on the same topic) and unacknowledged canonical tension (presenting one biblical voice as the biblical position when the scripture itself contains disagreement). Gospel citations are in ESV; OT and non-Gospel NT citations are in ESV.</p>
<p><strong>Transcript source:</strong> YouTube auto-captions (YouTube video ID {esc(yt)}). Auto-caption text may have minor transcription errors; quoted passages have been sanity-checked against the audio.</p>
<p style="margin-top:1rem;">Report generated {esc(generated_at)}.</p>
</footer>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("findings_json", type=Path)
    ap.add_argument("output_html", type=Path)
    ap.add_argument("--project-root", type=Path, default=None,
                    help="Directory that transcript_path in the JSON is relative to. "
                         "Defaults to the parent of findings_json.")
    args = ap.parse_args()

    data = json.loads(args.findings_json.read_text(encoding="utf-8"))
    root = args.project_root or args.findings_json.parent.parent
    transcript_path = root / data["meta"]["transcript_path"]
    paragraphs = parse_transcript(transcript_path)

    html_out = build_html(data, paragraphs)
    args.output_html.write_text(html_out, encoding="utf-8")
    print(f"Wrote {args.output_html} ({len(html_out):,} chars, "
          f"{len(paragraphs)} transcript paragraphs, "
          f"{len(data['findings'])} findings)", file=sys.stderr)


if __name__ == "__main__":
    main()
