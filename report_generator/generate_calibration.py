#!/usr/bin/env python3
"""Generate a focused calibration HTML: side-by-side per-marker comparison of N pastors.

Goes deeper than generate_comparison.py by showing, for each CN marker and each
Axis-2 sub-rubric, the exact status + note/quote from each pastor's findings
side-by-side. Intended for verifying that severity ratings are applied
consistently across pastors on the same topic.
"""
from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def fmt_big(n):
    if n is None:
        return "—"
    n = int(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n/1_000:.0f}K"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


CANON_MARKERS = [
    "A. Conflation of national & Christian identity",
    "B. Militaristic / warrior framing",
    "C. Political opponents as spiritual enemies",
    "D. Dominionist rhetoric",
    "E. Civil religion (flag, pledge)",
    'F. Jeremiad / "Christianity under attack"',
    'G. Ethno-cultural "real American" undertones',
    "H. Strongman / authoritarian affinity",
]

OTHER_AXIS2 = ["Anti-Muslim framing", "Anti-LGBTQ framing", "Misogynistic framing", "Anti-Jewish framing"]


def marker_by_prefix(findings: dict, prefix: str) -> dict | None:
    for m in findings.get("cn_markers", []):
        if m.get("marker", "").strip().startswith(prefix):
            return m
    return None


def other_rubric_by_name(findings: dict, name: str) -> dict | None:
    for r in findings.get("other_axis2_rubrics", []):
        rn = r.get("rubric", "").lower()
        key = name.split()[0].lower()  # "anti-muslim", "anti-lgbtq", etc.
        if key in rn:
            return r
    return None


def status_class(status: str) -> str:
    s = (status or "").lower()
    if "severe" in s or "high" in s:
        return "status-severe"
    if "present" in s or "moderate" in s:
        return "status-present"
    if "low" in s:
        return "status-low"
    return "status-none"


CSS = r"""
* { box-sizing: border-box; }
:root {
  --c-bg: #fafaf7; --c-fg: #1d1d1b; --c-muted: #6b6b67; --c-border: #d8d6cf;
  --c-card: #ffffff;
  --c-severe: #9b1c1c; --c-severe-bg: #fde8e8;
  --c-moderate: #c2410c; --c-moderate-bg: #ffedd5;
  --c-low: #a16207; --c-low-bg: #fef3c7;
  --c-link: #1e40af;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  background: var(--c-bg); color: var(--c-fg);
  max-width: 1400px; margin: 0 auto; padding: 2rem 1.5rem 5rem;
  line-height: 1.5;
}
h1 { font-size: 1.9rem; margin: 0 0 .25rem; letter-spacing: -0.01em; }
h2 { font-size: 1.3rem; margin: 2.5rem 0 .75rem; border-bottom: 1px solid var(--c-border); padding-bottom: .3rem; }
h3 { font-size: 1rem; margin: 1rem 0 .3rem; }
a { color: var(--c-link); text-decoration: none; border-bottom: 1px solid rgba(30,64,175,0.3); }

.pastor-cols { display: grid; gap: 1rem; }
.pastor-header-row { display: grid; gap: 1rem; }

.pastor-card {
  background: var(--c-card); border: 1px solid var(--c-border); border-radius: 6px;
  padding: .75rem 1rem;
}
.pastor-card .name { font-weight: 700; font-size: 1.05rem; }
.pastor-card .church { font-size: .82rem; color: var(--c-muted); }
.pastor-card .sermon { font-size: .82rem; margin-top: .3rem; font-style: italic; color: var(--c-muted); }
.pastor-card .reach-line { font-size: .78rem; margin-top: .4rem; font-variant-numeric: tabular-nums; color: var(--c-fg); }
.pastor-card .reach-line strong { font-weight: 700; }

.marker-row {
  display: grid; gap: 1rem; margin: .5rem 0; padding: .75rem;
  background: var(--c-card); border: 1px solid var(--c-border); border-radius: 6px;
}
.marker-row .marker-title {
  grid-column: 1 / -1;
  font-weight: 600; font-size: .9rem;
  color: var(--c-muted); text-transform: uppercase; letter-spacing: .05em;
  border-bottom: 1px dashed var(--c-border); padding-bottom: .25rem; margin-bottom: .25rem;
}
.marker-cell { font-size: .88rem; line-height: 1.45; }
.marker-cell .status-tag {
  display: inline-block; font-size: .7rem; font-weight: 600;
  padding: 2px 7px; border-radius: 3px;
  text-transform: uppercase; letter-spacing: .05em;
}
.marker-cell .status-tag.status-severe { background: var(--c-severe); color: white; }
.marker-cell .status-tag.status-present { background: var(--c-moderate); color: white; }
.marker-cell .status-tag.status-low { background: var(--c-low); color: white; }
.marker-cell .status-tag.status-none { background: #e5e2d8; color: var(--c-muted); }
.marker-cell .note { font-size: .82rem; color: var(--c-fg); margin-top: .4rem; padding: .4rem .55rem; background: #f5f4ee; border-radius: 3px; border-left: 2px solid var(--c-border); }

.axis2-headline {
  background: var(--c-card); border: 1px solid var(--c-border); border-radius: 6px;
  padding: .75rem 1rem; font-size: .9rem; line-height: 1.5;
}
.axis2-headline.severity-severe { border-left: 4px solid var(--c-severe); }
.axis2-headline.severity-moderate { border-left: 4px solid var(--c-moderate); }
.axis2-headline.severity-low { border-left: 4px solid var(--c-low); }
.axis2-headline .verdict-line { font-weight: 600; margin-bottom: .3rem; }
.axis2-headline .headline-body { color: var(--c-fg); font-size: .88rem; }

.finding-card {
  background: var(--c-card); border: 1px solid var(--c-border); border-radius: 6px;
  padding: .75rem 1rem; margin-top: .5rem; font-size: .88rem;
}
.finding-card.severity-severe { border-left: 4px solid var(--c-severe); }
.finding-card.severity-moderate { border-left: 4px solid var(--c-moderate); }
.finding-card.severity-low { border-left: 4px solid var(--c-low); }
.finding-card .finding-title { font-weight: 600; }
.finding-card .pastor-quote { font-size: .83rem; background: #fef7f4; padding: .4rem .55rem; border-radius: 3px; margin: .4rem 0; border-left: 2px solid #f3d6c5; }
.finding-card .why-flagged-short { font-size: .82rem; color: var(--c-muted); }

.severity-rank {
  background: var(--c-card); border: 1px solid var(--c-border); border-radius: 6px;
  padding: 1rem 1.25rem;
}
.severity-rank table { width: 100%; border-collapse: collapse; font-size: .9rem; }
.severity-rank th, .severity-rank td { text-align: left; padding: .4rem .5rem; border-bottom: 1px solid var(--c-border); }
.severity-rank th { background: #ebe9e1; font-weight: 600; font-size: .78rem; text-transform: uppercase; letter-spacing: .05em; }

footer { margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--c-border); color: var(--c-muted); font-size: .85rem; }
"""


def render_pastor_header(findings: dict) -> str:
    m = findings["meta"]
    r = findings.get("reach") or {}
    views = r.get("view_count")
    subs = r.get("channel_follower_count")
    cong = (r.get("congregation") or {}).get("weekly_attendance_est")
    audience_note = (r.get("congregation") or {}).get("audience_context")

    reach_parts = []
    if views is not None:
        reach_parts.append(f"<strong>{esc(fmt_big(views))}</strong> views")
    if subs is not None:
        reach_parts.append(f"<strong>{esc(fmt_big(subs))}</strong> subs")
    if cong is not None:
        reach_parts.append(f"~<strong>{esc(fmt_big(cong))}</strong>/wk")
    reach_line = " · ".join(reach_parts) if reach_parts else (esc(audience_note) if audience_note else "—")

    return (
        '<div class="pastor-card">'
        f'<div class="name">{esc(m["preacher"])}</div>'
        f'<div class="church">{esc(m["church"])}</div>'
        f'<div class="sermon">“{esc(m["sermon_title"][:70])}” ({esc(m["upload_date"])})</div>'
        f'<div class="reach-line">{reach_line}</div>'
        "</div>"
    )


def render_marker_row(sermons: list[dict], prefix: str, label: str) -> str:
    cells = ""
    for s in sermons:
        m = marker_by_prefix(s, prefix)
        status = (m or {}).get("status", "—")
        note = (m or {}).get("note", "") or (m or {}).get("reference", "")
        cls = status_class(status)
        note_html = f'<div class="note">{esc(note)}</div>' if note else ""
        cells += (
            '<div class="marker-cell">'
            f'<span class="status-tag {cls}">{esc(status)}</span>'
            f"{note_html}"
            "</div>"
        )
    return (
        '<div class="marker-row" style="grid-template-columns: repeat(' + str(len(sermons)) + ', 1fr);">'
        f'<div class="marker-title">{esc(label)}</div>'
        f"{cells}"
        "</div>"
    )


def render_other_rubric_row(sermons: list[dict], name: str) -> str:
    cells = ""
    for s in sermons:
        r = other_rubric_by_name(s, name)
        status = (r or {}).get("status", "—")
        note = (r or {}).get("note", "")
        cls = status_class(status)
        note_html = f'<div class="note">{esc(note)}</div>' if note else ""
        cells += (
            '<div class="marker-cell">'
            f'<span class="status-tag {cls}">{esc(status)}</span>'
            f"{note_html}"
            "</div>"
        )
    return (
        '<div class="marker-row" style="grid-template-columns: repeat(' + str(len(sermons)) + ', 1fr);">'
        f'<div class="marker-title">{esc(name)}</div>'
        f"{cells}"
        "</div>"
    )


def render_axis2_headline(findings: dict) -> str:
    ax2 = findings["scorecard"]["axis_2"]
    sev = ax2["severity"]
    return (
        f'<div class="axis2-headline severity-{esc(sev)}">'
        f'<div class="verdict-line">[{esc(sev)}] {esc(ax2["verdict"])}</div>'
        f'<div class="headline-body">{esc(ax2["headline"])}</div>'
        "</div>"
    )


def render_top_findings_col(findings: dict, axis: int, k: int = 2) -> str:
    """Render top N findings for a given axis, sorted by severity."""
    sev_rank = {"severe": 3, "moderate": 2, "low": 1, "none": 0}
    items = [f for f in findings.get("findings", []) if f.get("axis") == axis]
    items = sorted(items, key=lambda x: -sev_rank.get(x.get("severity", "low"), 0))[:k]
    cards = []
    for f in items:
        sev = f.get("severity", "low")
        pq = f.get("pastor_quote", "")
        if len(pq) > 220:
            pq = pq[:217] + "…"
        cards.append(
            f'<div class="finding-card severity-{esc(sev)}">'
            f'<div class="finding-title">{esc(f["title"])}</div>'
            f'<div class="pastor-quote">“{esc(pq)}”</div>'
            f'<div class="why-flagged-short">{esc(f.get("why_flagged", "")[:200])}</div>'
            "</div>"
        )
    return "".join(cards) or '<div style="font-size:.85rem;color:var(--c-muted);">(no findings at this axis)</div>'


def render_severity_ranking(sermons: list[dict]) -> str:
    """Compute reach-weighted severity ranking."""
    rows = []
    for s in sermons:
        m = s["meta"]
        sc = s["scorecard"]
        r = s.get("reach", {}) or {}
        views = r.get("view_count") or 0
        cong = (r.get("congregation") or {}).get("weekly_attendance_est") or 0
        cn_present = sum(
            1 for mk in s.get("cn_markers", [])
            if any(x in mk.get("status", "").lower() for x in ("present", "moderate", "high", "severe"))
        )
        # Annualized reach: YouTube views (one-time) + weekly congregation × 52
        annual_reach = views + cong * 52
        sev_rank = {"severe": 3, "moderate": 2, "low": 1, "none": 0}
        sev_score = sum(
            sev_rank.get(sc[k]["severity"], 0)
            for k in ("axis_1", "axis_2", "axis_3", "axis_4")
        )
        rows.append({
            "name": m["preacher"],
            "views": views,
            "weekly": cong,
            "annual": annual_reach,
            "cn": cn_present,
            "sev": sev_score,
            "axis2": sc["axis_2"]["severity"],
        })
    rows.sort(key=lambda r: -r["annual"])

    trs = []
    for r in rows:
        trs.append(
            f'<tr>'
            f'<td>{esc(r["name"])}</td>'
            f'<td>{esc(fmt_big(r["views"]))}</td>'
            f'<td>~{esc(fmt_big(r["weekly"]))}</td>'
            f'<td><strong>~{esc(fmt_big(r["annual"]))}</strong></td>'
            f'<td>{r["cn"]}/8</td>'
            f'<td>{r["sev"]}/12</td>'
            f'<td>{esc(r["axis2"])}</td>'
            f'</tr>'
        )
    return (
        '<div class="severity-rank">'
        "<table>"
        "<thead><tr><th>Pastor</th><th>YT views (1×)</th><th>Weekly</th>"
        "<th>Annualized reach</th><th>CN markers</th><th>Axis-sum</th><th>Axis 2</th></tr></thead>"
        f'<tbody>{"".join(trs)}</tbody>'
        "</table>"
        "<p style='font-size:.82rem;color:var(--c-muted);margin-top:.5rem;'>"
        "<em>Annualized reach</em> = YouTube views (one-time) + weekly congregation × 52. "
        "A rough aggregate of sermon-level plus congregation-level reach for the year following publication. "
        "Ordering by annualized reach surfaces who is likely to be heard the most, not who preaches the worst content. "
        "Pair with the CN-marker and axis-severity columns to see the combined picture."
        "</p>"
        "</div>"
    )


def build_html(sermons: list[dict]) -> str:
    n = len(sermons)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    grid_cols = f"grid-template-columns: repeat({n}, 1fr);"

    header_row = (
        f'<div class="pastor-header-row" style="{grid_cols}">'
        + "".join(render_pastor_header(s) for s in sermons)
        + "</div>"
    )

    axis2_headlines = (
        f'<div class="pastor-header-row" style="{grid_cols}">'
        + "".join(render_axis2_headline(s) for s in sermons)
        + "</div>"
    )

    top_findings = (
        f'<div class="pastor-header-row" style="{grid_cols}">'
        + "".join(f'<div>{render_top_findings_col(s, axis=2, k=3)}</div>' for s in sermons)
        + "</div>"
    )

    cn_rows = "\n".join(render_marker_row(sermons, c[:2], c) for c in CANON_MARKERS)
    other_rows = "\n".join(render_other_rubric_row(sermons, r) for r in OTHER_AXIS2)

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>whosaid — Calibration Comparison</title>
<style>{CSS}</style>
</head><body>
<div style="font-size:.75rem; color: var(--c-muted); letter-spacing:.1em; text-transform: uppercase;">Calibration — side-by-side per-marker comparison</div>
<h1>whosaid — Calibration Comparison</h1>
<p style="color: var(--c-muted); margin-top:.5rem;">Cross-checks that severity ratings are applied consistently across {n} pastors on the same topic. For each CN marker and Axis-2 sub-rubric, shows the status + supporting note/evidence from each pastor's findings side-by-side.</p>

<h2>Pastors</h2>
{header_row}

<h2>Axis 2 — Headline Verdict</h2>
{axis2_headlines}

<h2>Axis 2 — Top Findings (with pastor quote)</h2>
{top_findings}

<h2>Christian Nationalism Markers — Side by Side</h2>
{cn_rows}

<h2>Other Axis-2 Sub-Rubrics — Side by Side</h2>
{other_rows}

<h2>Reach-Weighted Severity Ranking</h2>
{render_severity_ranking(sermons)}

<footer>
<p>Calibration generated {esc(generated_at)} from {n} findings JSON files. Methodology and rubrics: see any individual report's footer.</p>
</footer>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("findings", nargs="+", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    sermons = [json.loads(p.read_text(encoding="utf-8")) for p in args.findings]
    html_out = build_html(sermons)
    args.output.write_text(html_out, encoding="utf-8")
    print(f"Wrote {args.output} ({len(html_out):,} chars, {len(sermons)} sermons)")


if __name__ == "__main__":
    main()
