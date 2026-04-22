#!/usr/bin/env python3
"""Generate a longitudinal (time-series) comparison for the same pastor.

Takes exactly two findings JSONs from the same preacher and shows the delta:
severity shifts per axis, CN-marker deltas (appeared / disappeared / upgraded /
downgraded), reach comparison, and side-by-side headline quotes.
"""
from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path


SEV_RANK = {"severe": 3, "moderate": 2, "low": 1, "none": 0}


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


def status_rank(status: str) -> int:
    s = (status or "").lower()
    if "severe" in s or "high" in s:
        return 3
    if "present" in s or "moderate" in s:
        return 2
    if "low" in s:
        return 1
    return 0


def status_class(status: str) -> str:
    r = status_rank(status)
    return {3: "status-severe", 2: "status-present", 1: "status-low", 0: "status-none"}[r]


def delta_arrow(r0: int, r1: int) -> tuple[str, str]:
    """Return (arrow, css-class) representing change from r0 → r1."""
    if r1 > r0:
        return ("↑", "delta-up")
    if r1 < r0:
        return ("↓", "delta-down")
    return ("=", "delta-same")


def marker_by_prefix(s: dict, prefix: str) -> dict | None:
    for m in s.get("cn_markers", []):
        if m.get("marker", "").strip().startswith(prefix):
            return m
    return None


def other_by_name(s: dict, name: str) -> dict | None:
    key = name.split()[0].lower()
    for r in s.get("other_axis2_rubrics", []):
        if key in r.get("rubric", "").lower():
            return r
    return None


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


CSS = r"""
* { box-sizing: border-box; }
:root {
  --c-bg: #fafaf7; --c-fg: #1d1d1b; --c-muted: #6b6b67; --c-border: #d8d6cf;
  --c-card: #ffffff;
  --c-severe: #9b1c1c; --c-severe-bg: #fde8e8;
  --c-moderate: #c2410c; --c-moderate-bg: #ffedd5;
  --c-low: #a16207; --c-low-bg: #fef3c7;
  --c-link: #1e40af;
  --c-up: #9b1c1c; --c-down: #166534; --c-same: #6b6b67;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  background: var(--c-bg); color: var(--c-fg);
  max-width: 1100px; margin: 0 auto; padding: 2rem 1.5rem 5rem;
  line-height: 1.55;
}
h1 { font-size: 2rem; margin: 0 0 .25rem; letter-spacing: -0.01em; }
h2 { font-size: 1.35rem; margin: 2.5rem 0 .75rem; border-bottom: 1px solid var(--c-border); padding-bottom: .3rem; }
h3 { font-size: 1rem; margin: 1rem 0 .4rem; }
a { color: var(--c-link); text-decoration: none; border-bottom: 1px solid rgba(30,64,175,0.3); }

.time-header { display: grid; grid-template-columns: 1fr 60px 1fr; gap: 1rem; align-items: stretch; margin: 1.5rem 0; }
.time-header .time-card { background: var(--c-card); border: 1px solid var(--c-border); border-radius: 6px; padding: 1rem 1.25rem; }
.time-header .time-card .label { font-size: .68rem; color: var(--c-muted); letter-spacing: .1em; text-transform: uppercase; margin-bottom: .3rem; }
.time-header .time-card .date { font-family: 'SF Mono', Menlo, monospace; font-size: .9rem; color: var(--c-muted); margin-bottom: .3rem; }
.time-header .time-card .sermon-title { font-size: 1.05rem; font-weight: 600; line-height: 1.3; margin-bottom: .4rem; }
.time-header .time-card .church-line { font-size: .82rem; color: var(--c-muted); margin-bottom: .4rem; }
.time-header .time-card .reach-line { font-size: .82rem; font-variant-numeric: tabular-nums; margin-top: .5rem; padding-top: .5rem; border-top: 1px dashed var(--c-border); }
.time-header .arrow { display: flex; align-items: center; justify-content: center; font-size: 2rem; color: var(--c-muted); font-weight: 300; }

.axis-grid { display: grid; grid-template-columns: 1fr; gap: .5rem; }
.axis-row {
  display: grid; grid-template-columns: 200px 1fr 60px 1fr;
  gap: 1rem; align-items: center;
  background: var(--c-card); border: 1px solid var(--c-border); border-radius: 6px;
  padding: .65rem 1rem;
}
.axis-row .axis-label { font-weight: 600; font-size: .9rem; }
.axis-row .verdict-cell { font-size: .85rem; line-height: 1.35; }
.axis-row .verdict-cell .verdict-text { color: var(--c-muted); font-size: .8rem; margin-top: .15rem; }
.axis-row .delta-cell { text-align: center; font-size: 1.6rem; font-weight: 700; }
.axis-row .delta-cell .delta-up { color: var(--c-up); }
.axis-row .delta-cell .delta-down { color: var(--c-down); }
.axis-row .delta-cell .delta-same { color: var(--c-same); }
.axis-row .delta-cell .delta-label { display: block; font-size: .65rem; font-weight: 400; letter-spacing: .05em; text-transform: uppercase; color: var(--c-muted); margin-top: -.15rem; }

.sev-badge {
  display: inline-block; font-size: 0.68rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.06em;
  padding: 2px 7px; border-radius: 3px; color: white;
}
.sev-badge.sev-severe { background: var(--c-severe); }
.sev-badge.sev-moderate { background: var(--c-moderate); }
.sev-badge.sev-low { background: var(--c-low); }
.sev-badge.sev-none { background: #6b6b67; }

.marker-table {
  width: 100%; border-collapse: collapse; font-size: .88rem;
  background: var(--c-card); border: 1px solid var(--c-border); border-radius: 6px; overflow: hidden;
}
.marker-table th, .marker-table td { padding: .5rem .7rem; border-bottom: 1px solid var(--c-border); text-align: left; vertical-align: top; }
.marker-table th { background: #ebe9e1; font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; }
.marker-table tr:last-child td { border-bottom: 0; }
.marker-table td.status-cell { min-width: 95px; font-size: .82rem; }
.marker-table td.delta-cell { text-align: center; font-size: 1.3rem; font-weight: 700; width: 50px; }
.marker-table .status-tag {
  display: inline-block; font-size: .65rem; font-weight: 600;
  padding: 1px 6px; border-radius: 3px;
  text-transform: uppercase; letter-spacing: .04em;
}
.marker-table .status-tag.status-severe { background: var(--c-severe); color: white; }
.marker-table .status-tag.status-present { background: var(--c-moderate); color: white; }
.marker-table .status-tag.status-low { background: var(--c-low); color: white; }
.marker-table .status-tag.status-none { background: #e5e2d8; color: var(--c-muted); }
.marker-table .delta-up { color: var(--c-up); }
.marker-table .delta-down { color: var(--c-down); }
.marker-table .delta-same { color: var(--c-same); font-size: 1rem; opacity: .6; }
.marker-table .delta-appeared { color: var(--c-up); }

.headline-compare {
  display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin: .5rem 0;
}
@media (max-width: 700px) { .headline-compare { grid-template-columns: 1fr; } }
.headline-block {
  background: var(--c-card); border: 1px solid var(--c-border); border-radius: 6px;
  padding: .75rem 1rem; font-size: .9rem;
}
.headline-block.severity-severe { border-left: 4px solid var(--c-severe); }
.headline-block.severity-moderate { border-left: 4px solid var(--c-moderate); }
.headline-block.severity-low { border-left: 4px solid var(--c-low); }
.headline-block .date-line { font-size: .72rem; color: var(--c-muted); text-transform: uppercase; letter-spacing: .06em; margin-bottom: .3rem; }
.headline-block .verdict-line { font-weight: 600; margin-bottom: .3rem; }
.headline-block .headline-body { font-size: .88rem; color: var(--c-fg); }

.finding-preview {
  background: #f9f7ed; border-left: 3px solid var(--c-border); border-radius: 0 3px 3px 0;
  padding: .5rem .7rem; margin-top: .4rem; font-size: .83rem;
}
.finding-preview .title { font-weight: 600; }
.finding-preview .quote { font-style: italic; color: var(--c-muted); margin-top: .2rem; }

.summary-box {
  background: var(--c-card); border: 1px solid var(--c-border); border-radius: 6px;
  padding: 1rem 1.25rem; margin: 1rem 0;
}

footer { margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--c-border); color: var(--c-muted); font-size: .85rem; }
"""


def render_time_card(s: dict, label: str) -> str:
    m = s["meta"]; r = s.get("reach") or {}
    views = r.get("view_count")
    subs = r.get("channel_follower_count")
    cong = (r.get("congregation") or {}).get("weekly_attendance_est")
    reach_parts = []
    if views is not None:
        reach_parts.append(f"<strong>{esc(fmt_big(views))}</strong> views")
    if subs is not None:
        reach_parts.append(f"<strong>{esc(fmt_big(subs))}</strong> subs")
    if cong is not None:
        reach_parts.append(f"~<strong>{esc(fmt_big(cong))}</strong>/wk")
    reach_line = " · ".join(reach_parts) if reach_parts else "—"

    return (
        '<div class="time-card">'
        f'<div class="label">{esc(label)}</div>'
        f'<div class="date">{esc(m["upload_date"])}</div>'
        f'<div class="sermon-title">{esc(m["sermon_title"])}</div>'
        f'<div class="church-line">{esc(m["church"])}</div>'
        f'<div class="reach-line">{reach_line}</div>'
        "</div>"
    )


def render_axis_rows(s0: dict, s1: dict) -> str:
    axis_labels = {
        "axis_1": "Axis 1 — Jesus",
        "axis_2": "Axis 2 — Bias/Harm",
        "axis_3": "Axis 3 — Facts",
        "axis_4": "Axis 4 — Whole Bible",
    }
    rows = []
    for key, label in axis_labels.items():
        sc0 = s0["scorecard"][key]
        sc1 = s1["scorecard"][key]
        r0 = SEV_RANK.get(sc0["severity"], 0)
        r1 = SEV_RANK.get(sc1["severity"], 0)
        arrow, arrow_cls = delta_arrow(r0, r1)
        arrow_label = {"delta-up": "escalated", "delta-down": "moderated", "delta-same": "unchanged"}[arrow_cls]
        rows.append(
            '<div class="axis-row">'
            f'<div class="axis-label">{esc(label)}</div>'
            '<div class="verdict-cell">'
            f'<span class="sev-badge sev-{esc(sc0["severity"])}">{esc(sc0["severity"])}</span>'
            f'<div class="verdict-text">{esc(sc0["verdict"][:80])}</div>'
            '</div>'
            f'<div class="delta-cell"><span class="{arrow_cls}">{arrow}</span><span class="delta-label">{arrow_label}</span></div>'
            '<div class="verdict-cell">'
            f'<span class="sev-badge sev-{esc(sc1["severity"])}">{esc(sc1["severity"])}</span>'
            f'<div class="verdict-text">{esc(sc1["verdict"][:80])}</div>'
            '</div>'
            '</div>'
        )
    return '<div class="axis-grid">' + "".join(rows) + "</div>"


def render_marker_comparison(s0: dict, s1: dict) -> str:
    rows = []
    for canon in CANON_MARKERS:
        prefix = canon[:2]
        m0 = marker_by_prefix(s0, prefix)
        m1 = marker_by_prefix(s1, prefix)
        st0 = (m0 or {}).get("status", "—")
        st1 = (m1 or {}).get("status", "—")
        r0 = status_rank(st0)
        r1 = status_rank(st1)
        if r0 == 0 and r1 > 0:
            arrow, arrow_cls = "+", "delta-appeared"
        elif r0 > 0 and r1 == 0:
            arrow, arrow_cls = "−", "delta-down"
        else:
            arrow, arrow_cls = delta_arrow(r0, r1)
        rows.append(
            "<tr>"
            f'<td>{esc(canon)}</td>'
            f'<td class="status-cell"><span class="status-tag {status_class(st0)}">{esc(st0)}</span></td>'
            f'<td class="delta-cell {arrow_cls}">{arrow}</td>'
            f'<td class="status-cell"><span class="status-tag {status_class(st1)}">{esc(st1)}</span></td>'
            "</tr>"
        )
    return (
        '<table class="marker-table">'
        "<thead><tr><th>CN Marker</th><th>Then</th><th>Δ</th><th>Now</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def render_other_axis2_comparison(s0: dict, s1: dict) -> str:
    rows = []
    for name in OTHER_AXIS2:
        r0 = other_by_name(s0, name)
        r1 = other_by_name(s1, name)
        st0 = (r0 or {}).get("status", "—")
        st1 = (r1 or {}).get("status", "—")
        rank0, rank1 = status_rank(st0), status_rank(st1)
        if rank0 == 0 and rank1 > 0:
            arrow, arrow_cls = "+", "delta-appeared"
        elif rank0 > 0 and rank1 == 0:
            arrow, arrow_cls = "−", "delta-down"
        else:
            arrow, arrow_cls = delta_arrow(rank0, rank1)
        rows.append(
            "<tr>"
            f'<td>{esc(name)}</td>'
            f'<td class="status-cell"><span class="status-tag {status_class(st0)}">{esc(st0)}</span></td>'
            f'<td class="delta-cell {arrow_cls}">{arrow}</td>'
            f'<td class="status-cell"><span class="status-tag {status_class(st1)}">{esc(st1)}</span></td>'
            "</tr>"
        )
    return (
        '<table class="marker-table">'
        "<thead><tr><th>Sub-rubric</th><th>Then</th><th>Δ</th><th>Now</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def render_axis2_headlines(s0: dict, s1: dict) -> str:
    ax0 = s0["scorecard"]["axis_2"]
    ax1 = s1["scorecard"]["axis_2"]

    # Pull top severity finding from each for illustration
    def top_axis2_finding(s):
        items = [f for f in s.get("findings", []) if f.get("axis") == 2]
        items.sort(key=lambda x: -SEV_RANK.get(x.get("severity", "low"), 0))
        return items[0] if items else None

    t0 = top_axis2_finding(s0)
    t1 = top_axis2_finding(s1)

    def block(s, ax, top, label):
        sev = ax["severity"]
        preview = ""
        if top:
            pq = top.get("pastor_quote", "")
            if len(pq) > 250:
                pq = pq[:247] + "…"
            preview = (
                '<div class="finding-preview">'
                f'<div class="title">Top Axis-2 finding: {esc(top["title"])}</div>'
                f'<div class="quote">“{esc(pq)}”</div>'
                '</div>'
            )
        return (
            f'<div class="headline-block severity-{esc(sev)}">'
            f'<div class="date-line">{esc(label)} · {esc(s["meta"]["upload_date"])}</div>'
            f'<div class="verdict-line">[{esc(sev)}] {esc(ax["verdict"])}</div>'
            f'<div class="headline-body">{esc(ax["headline"])}</div>'
            f"{preview}"
            "</div>"
        )

    return (
        '<div class="headline-compare">'
        + block(s0, ax0, t0, "Then") + block(s1, ax1, t1, "Now")
        + "</div>"
    )


def compute_summary(s0: dict, s1: dict) -> str:
    # Axis severity deltas
    deltas = []
    for key, label in [
        ("axis_1", "Axis 1"),
        ("axis_2", "Axis 2"),
        ("axis_3", "Axis 3"),
        ("axis_4", "Axis 4"),
    ]:
        r0 = SEV_RANK.get(s0["scorecard"][key]["severity"], 0)
        r1 = SEV_RANK.get(s1["scorecard"][key]["severity"], 0)
        if r1 > r0:
            deltas.append(f"{label} escalated ({s0['scorecard'][key]['severity']} → {s1['scorecard'][key]['severity']})")
        elif r1 < r0:
            deltas.append(f"{label} moderated ({s0['scorecard'][key]['severity']} → {s1['scorecard'][key]['severity']})")

    # CN markers appeared/disappeared
    appeared, disappeared, upgraded = [], [], []
    for canon in CANON_MARKERS:
        prefix = canon[:2]
        m0 = marker_by_prefix(s0, prefix)
        m1 = marker_by_prefix(s1, prefix)
        r0 = status_rank((m0 or {}).get("status", ""))
        r1 = status_rank((m1 or {}).get("status", ""))
        if r0 == 0 and r1 > 0:
            appeared.append(canon[:30])
        elif r0 > 0 and r1 == 0:
            disappeared.append(canon[:30])
        elif r1 > r0:
            upgraded.append(canon[:30])

    parts = []
    if deltas:
        parts.append("<li>" + " · ".join(deltas) + "</li>")
    if appeared:
        parts.append(f"<li><strong>CN markers appeared:</strong> {', '.join(appeared)}</li>")
    if upgraded:
        parts.append(f"<li><strong>CN markers upgraded:</strong> {', '.join(upgraded)}</li>")
    if disappeared:
        parts.append(f"<li><strong>CN markers disappeared:</strong> {', '.join(disappeared)}</li>")
    if not parts:
        parts.append("<li>No axis-severity or CN-marker changes between the two sermons.</li>")
    return '<div class="summary-box"><h3 style="margin-top:0;">At a glance</h3><ul style="margin:.25rem 0 0 1.2rem; padding:0;">' + "".join(parts) + "</ul></div>"


def build_html(s0: dict, s1: dict) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Validate same preacher
    p0 = s0["meta"]["preacher"]
    p1 = s1["meta"]["preacher"]
    same_preacher = p0 == p1

    date_0 = s0["meta"]["upload_date"]
    date_1 = s1["meta"]["upload_date"]
    years_apart = "?"
    try:
        d0 = datetime.strptime(date_0, "%Y-%m-%d")
        d1 = datetime.strptime(date_1, "%Y-%m-%d")
        years_apart = f"{(d1 - d0).days / 365.25:.1f}"
    except Exception:
        pass

    warning = ""
    if not same_preacher:
        warning = f'<div style="background:#fff3cd;border:1px solid #ffc107;padding:.6rem .8rem;border-radius:4px;margin:1rem 0;">⚠ Warning: findings are from different preachers ({esc(p0)} vs. {esc(p1)}).</div>'

    header = (
        '<div class="time-header">'
        f"{render_time_card(s0, 'Then')}"
        '<div class="arrow">→</div>'
        f"{render_time_card(s1, 'Now')}"
        "</div>"
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>whosaid — Longitudinal: {esc(p0)}</title>
<style>{CSS}</style>
</head><body>

<div style="font-size:.75rem; color: var(--c-muted); letter-spacing:.1em; text-transform: uppercase;">Longitudinal comparison · same pastor, across time</div>
<h1>{esc(p0)}</h1>
<p style="color: var(--c-muted); margin:.3rem 0 1rem; font-size: 1rem;">{esc(date_0)} &nbsp;→&nbsp; {esc(date_1)} &nbsp;<span style="color:var(--c-muted);font-size:.9rem;">({years_apart} years apart)</span></p>

{warning}
{header}

{compute_summary(s0, s1)}

<h2>Axis Severity: Then vs. Now</h2>
{render_axis_rows(s0, s1)}

<h2>Axis 2 Headline Comparison</h2>
{render_axis2_headlines(s0, s1)}

<h2>Christian Nationalism Markers: Δ Over Time</h2>
{render_marker_comparison(s0, s1)}

<h2>Other Axis-2 Sub-rubrics: Δ Over Time</h2>
{render_other_axis2_comparison(s0, s1)}

<footer>
<p>A longitudinal pair is one snapshot vs. another — not a continuous trajectory. Intermediate sermons may show different patterns. Rendered {esc(generated_at)}.</p>
</footer>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("then", type=Path, help="Earlier findings JSON")
    ap.add_argument("now", type=Path, help="Later findings JSON")
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    s0 = json.loads(args.then.read_text(encoding="utf-8"))
    s1 = json.loads(args.now.read_text(encoding="utf-8"))

    # Ensure chronological order
    if s0["meta"]["upload_date"] > s1["meta"]["upload_date"]:
        s0, s1 = s1, s0

    html_out = build_html(s0, s1)
    args.output.write_text(html_out, encoding="utf-8")
    print(f"Wrote {args.output} ({len(html_out):,} chars)")


if __name__ == "__main__":
    main()
