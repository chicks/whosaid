#!/usr/bin/env python3
"""Generate a cross-sermon comparison HTML from multiple findings JSONs."""
from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path

SEV_RANK = {"severe": 3, "moderate": 2, "low": 1, "none": 0}
VERDICT_CLASS = {
    "supported": "supported",
    "partially supported": "partial",
    "partially supported / overstated": "partial",
    "contested": "contested",
    "misleading": "misleading",
    "unsupported": "unsupported",
    "false": "false",
    "needs verification": "unsupported",
}


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def sev_badge(sev: str) -> str:
    return f'<span class="sev-badge sev-{esc(sev)}">{esc(sev)}</span>'


def load_findings(paths: list[Path]) -> list[dict]:
    out = []
    for p in sorted(paths):
        data = json.loads(p.read_text(encoding="utf-8"))
        data["_source_path"] = p
        data["_report_name"] = p.stem + ".html"
        out.append(data)
    return out


CSS = r"""
* { box-sizing: border-box; }
:root {
  --c-bg: #fafaf7; --c-fg: #1d1d1b; --c-muted: #6b6b67; --c-border: #d8d6cf;
  --c-card: #ffffff;
  --c-severe: #9b1c1c; --c-severe-bg: #fde8e8;
  --c-moderate: #c2410c; --c-moderate-bg: #ffedd5;
  --c-low: #a16207; --c-low-bg: #fef3c7;
  --c-none: #6b6b67;
  --c-link: #1e40af;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  background: var(--c-bg); color: var(--c-fg);
  max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem 5rem;
  line-height: 1.55;
}
h1 { font-size: 2rem; margin: 0 0 .25rem; letter-spacing: -0.01em; }
h2 { font-size: 1.4rem; margin: 2.5rem 0 .75rem; border-bottom: 1px solid var(--c-border); padding-bottom: .3rem; }
h3 { font-size: 1.05rem; margin: 1rem 0 .3rem; }
a { color: var(--c-link); text-decoration: none; border-bottom: 1px solid rgba(30,64,175,0.3); }
a:hover { border-bottom-color: var(--c-link); }

.hero-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: .75rem; margin: 1rem 0; }
.stat { background: var(--c-card); border: 1px solid var(--c-border); border-radius: 6px; padding: .75rem; }
.stat .label { font-size: .7rem; color: var(--c-muted); text-transform: uppercase; letter-spacing: .08em; }
.stat .value { font-size: 1.4rem; font-weight: 600; margin-top: .2rem; }

.matrix { width: 100%; border-collapse: collapse; font-size: .9rem; background: var(--c-card); border: 1px solid var(--c-border); border-radius: 6px; overflow: hidden; }
.matrix th, .matrix td { padding: .6rem .75rem; border-bottom: 1px solid var(--c-border); text-align: left; vertical-align: top; }
.matrix th { background: #ebe9e1; font-weight: 600; font-size: .78rem; text-transform: uppercase; letter-spacing: .05em; }
.matrix tr:last-child td { border-bottom: 0; }
.matrix td.pastor-cell { min-width: 180px; }
.matrix td.pastor-cell .name { font-weight: 600; }
.matrix td.pastor-cell .church { font-size: .78rem; color: var(--c-muted); }
.matrix td.pastor-cell .sermon { font-size: .78rem; color: var(--c-muted); font-style: italic; margin-top: .2rem; }
.matrix td.sev-cell { min-width: 150px; }
.matrix td.sev-cell .verdict-line { font-size: .82rem; color: var(--c-muted); margin-top: .25rem; line-height: 1.3; }
.matrix td.reach-cell { min-width: 110px; font-size: .82rem; font-variant-numeric: tabular-nums; line-height: 1.4; }
.matrix td.reach-cell .reach-label { color: var(--c-muted); font-size: .7rem; text-transform: uppercase; letter-spacing: .05em; }
.matrix td.reach-cell .reach-note { color: var(--c-muted); font-style: italic; font-size: .78rem; line-height: 1.3; }

.sev-badge {
  display: inline-block; font-size: 0.68rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.06em;
  padding: 2px 7px; border-radius: 3px; color: white;
}
.sev-badge.sev-severe { background: var(--c-severe); }
.sev-badge.sev-moderate { background: var(--c-moderate); }
.sev-badge.sev-low { background: var(--c-low); }
.sev-badge.sev-none { background: var(--c-none); }

.verdict-badge {
  display: inline-block; font-size: 0.68rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.04em;
  padding: 2px 6px; border-radius: 3px; color: white;
}
.verdict-badge.verdict-supported { background: #166534; }
.verdict-badge.verdict-partial { background: #c2410c; }
.verdict-badge.verdict-contested { background: #a16207; }
.verdict-badge.verdict-misleading { background: #c2410c; }
.verdict-badge.verdict-unsupported { background: #6b6b67; }
.verdict-badge.verdict-false { background: var(--c-severe); }

.cn-matrix { width: 100%; border-collapse: collapse; font-size: .82rem; background: var(--c-card); border: 1px solid var(--c-border); border-radius: 6px; overflow: hidden; }
.cn-matrix th, .cn-matrix td { padding: .45rem .55rem; border-bottom: 1px solid var(--c-border); text-align: center; }
.cn-matrix th.pastor-header { writing-mode: vertical-rl; transform: rotate(180deg); white-space: nowrap; }
.cn-matrix th:first-child, .cn-matrix td:first-child { text-align: left; font-weight: 500; }
.cn-matrix th { background: #ebe9e1; font-size: .7rem; text-transform: uppercase; letter-spacing: .05em; vertical-align: bottom; }
.status-present { background: var(--c-severe-bg); color: var(--c-severe); font-weight: 600; }
.status-low { background: var(--c-low-bg); color: var(--c-low); }
.status-none { background: #f5f4ee; color: var(--c-muted); }

.axis-section { margin: 1rem 0; padding: 1rem 1.25rem; background: var(--c-card); border: 1px solid var(--c-border); border-radius: 6px; }
.axis-section.severe-left { border-left: 4px solid var(--c-severe); }
.axis-section.moderate-left { border-left: 4px solid var(--c-moderate); }
.axis-section.low-left { border-left: 4px solid var(--c-low); }
.axis-per-pastor { margin: .75rem 0 .25rem; }
.axis-per-pastor .row { display: grid; grid-template-columns: 220px auto 1fr; gap: .75rem; padding: .5rem 0; border-top: 1px dashed var(--c-border); align-items: start; }
.axis-per-pastor .row:first-child { border-top: 0; }
.axis-per-pastor .pastor-col { font-weight: 600; }
.axis-per-pastor .pastor-col .church { font-weight: 400; font-size: .8rem; color: var(--c-muted); }
.axis-per-pastor .sev-col { white-space: nowrap; }
.axis-per-pastor .headline { font-size: .92rem; }
.axis-per-pastor .report-link { font-size: .75rem; margin-top: .3rem; display: inline-block; }

.facts-summary { background: var(--c-card); border: 1px solid var(--c-border); border-radius: 6px; padding: 1rem; }
.facts-bars { display: grid; grid-template-columns: 120px auto 1fr; gap: .5rem; align-items: center; font-size: .88rem; margin: .3rem 0; }
.facts-bars .bar { height: 18px; border-radius: 3px; }
.facts-bars .bar.supported { background: #166534; }
.facts-bars .bar.partial, .facts-bars .bar.misleading { background: #c2410c; }
.facts-bars .bar.contested { background: #a16207; }
.facts-bars .bar.unsupported { background: #6b6b67; }
.facts-bars .bar.false { background: var(--c-severe); }

footer { margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--c-border); color: var(--c-muted); font-size: .85rem; }
footer h3 { font-size: .95rem; color: var(--c-fg); margin-bottom: .3rem; }
"""


def render_hero(findings: list[dict]) -> str:
    n = len(findings)
    total_findings = sum(len(f.get("findings", [])) for f in findings)
    total_axis4 = sum(len(f.get("axis4_findings", [])) for f in findings)
    total_facts = sum(len(f.get("factual_claims", [])) for f in findings)
    total_runtime = sum(f["meta"].get("runtime_seconds", 0) for f in findings)
    dates = sorted(f["meta"]["upload_date"] for f in findings)
    date_range = f"{dates[0]} → {dates[-1]}" if dates else ""

    total_views = sum((f.get("reach") or {}).get("view_count") or 0 for f in findings)
    total_weekly = sum(((f.get("reach") or {}).get("congregation") or {}).get("weekly_attendance_est") or 0 for f in findings)

    def fmt_big(n):
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.0f}K" if n >= 10_000 else f"{n/1_000:.1f}K"
        return str(n)

    stats = [
        ("Pastors audited", str(n)),
        ("Sermons", str(n)),
        ("Axis 1/2 findings", str(total_findings)),
        ("Axis 4 findings", str(total_axis4)),
        ("Factual claims", str(total_facts)),
        ("Total runtime", f"{total_runtime // 3600}h {(total_runtime % 3600) // 60}m"),
        ("YouTube views (aggregate)", fmt_big(total_views) if total_views else "—"),
        ("Weekly congregation (aggregate)", f"~{fmt_big(total_weekly)}"),
        ("Date range", date_range),
    ]
    cells = "".join(
        f'<div class="stat"><div class="label">{esc(k)}</div><div class="value">{esc(v)}</div></div>'
        for k, v in stats
    )
    return f'<div class="hero-stats">{cells}</div>'


def fmt_count(n) -> str:
    if n is None:
        return "—"
    n = int(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M".rstrip("0").rstrip(".") + "M" if False else f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K" if n >= 10_000 else f"{n/1_000:.1f}K"
    return str(n)


def render_reach_cell(f: dict) -> str:
    reach = f.get("reach") or {}
    views = reach.get("view_count")
    subs = reach.get("channel_follower_count")
    cong = (reach.get("congregation") or {}).get("weekly_attendance_est")
    audience_context = (reach.get("congregation") or {}).get("audience_context")

    parts = []
    if views is not None:
        parts.append(f'<div><span class="reach-label">views:</span> <strong>{esc(fmt_count(views))}</strong></div>')
    if subs is not None:
        parts.append(f'<div><span class="reach-label">subs:</span> <strong>{esc(fmt_count(subs))}</strong></div>')
    if cong is not None:
        parts.append(f'<div><span class="reach-label">weekly:</span> <strong>~{esc(fmt_count(cong))}</strong></div>')
    elif audience_context:
        parts.append(f'<div class="reach-note">{esc(audience_context[:80])}</div>')
    if not parts:
        parts = ['<div class="reach-note">—</div>']
    return '<td class="reach-cell">' + "".join(parts) + "</td>"


def render_scorecard_matrix(findings: list[dict]) -> str:
    rows = []
    # Sort: pastors with highest aggregate severity first
    def agg_sev(f):
        sc = f["scorecard"]
        return sum(SEV_RANK.get(sc[k]["severity"], 0) for k in ("axis_1", "axis_2", "axis_3", "axis_4"))
    findings_sorted = sorted(findings, key=lambda f: -agg_sev(f))

    for f in findings_sorted:
        m = f["meta"]
        sc = f["scorecard"]
        pastor_cell = (
            f'<td class="pastor-cell">'
            f'<div class="name">{esc(m["preacher"])}</div>'
            f'<div class="church">{esc(m["church"])}</div>'
            f'<div class="sermon">{esc(m["sermon_title"][:70])}</div>'
            f'<div style="margin-top:.3rem; font-size:.75rem;"><a href="{esc(f["_report_name"])}">full report →</a></div>'
            f'</td>'
        )
        reach_cell = render_reach_cell(f)
        axis_cells = ""
        for k in ("axis_1", "axis_2", "axis_3", "axis_4"):
            sev = sc[k]["severity"]
            verdict = sc[k]["verdict"]
            axis_cells += (
                f'<td class="sev-cell">'
                f'{sev_badge(sev)}'
                f'<div class="verdict-line">{esc(verdict)}</div>'
                f'</td>'
            )
        rows.append(f"<tr>{pastor_cell}{reach_cell}{axis_cells}</tr>")

    return (
        '<table class="matrix">'
        "<thead><tr>"
        "<th>Pastor / Sermon</th>"
        "<th>Reach</th>"
        "<th>Axis 1 — Jesus</th>"
        "<th>Axis 2 — Bias/Harm</th>"
        "<th>Axis 3 — Facts</th>"
        "<th>Axis 4 — Whole Bible</th>"
        "</tr></thead>"
        f'<tbody>{"".join(rows)}</tbody>'
        "</table>"
    )


def render_axis_section(findings: list[dict], axis_key: str, axis_label: str) -> str:
    rows = []
    findings_sorted = sorted(
        findings, key=lambda f: -SEV_RANK.get(f["scorecard"][axis_key]["severity"], 0)
    )
    max_sev = "low"
    for f in findings_sorted:
        m = f["meta"]
        sc = f["scorecard"][axis_key]
        sev = sc["severity"]
        if SEV_RANK.get(sev, 0) > SEV_RANK.get(max_sev, 0):
            max_sev = sev
        rows.append(
            f'<div class="row">'
            f'<div class="pastor-col">{esc(m["preacher"])}<div class="church">{esc(m["church"])}</div></div>'
            f'<div class="sev-col">{sev_badge(sev)}</div>'
            f'<div>'
            f'<div class="headline"><strong>{esc(sc["verdict"])}.</strong> {esc(sc["headline"])}</div>'
            f'<a class="report-link" href="{esc(f["_report_name"])}">full report →</a>'
            f'</div>'
            f'</div>'
        )
    return (
        f'<section class="axis-section {max_sev}-left">'
        f"<h3>{esc(axis_label)}</h3>"
        f'<div class="axis-per-pastor">{"".join(rows)}</div>'
        f"</section>"
    )


def normalize_cn_status(status: str) -> str:
    s = status.lower()
    if "present" in s or "high" in s or "severe" in s or "moderate" in s:
        return "present"
    if "low" in s:
        return "low"
    return "none"


def render_cn_matrix(findings: list[dict]) -> str:
    # Collect all unique markers across sermons to accommodate variation in marker labeling
    # (CN rubric is 8 rows but label text may vary slightly)
    canonical = [
        "A. Conflation of national & Christian identity",
        "B. Militaristic / warrior framing",
        "C. Political opponents as spiritual enemies",
        "D. Dominionist rhetoric",
        "E. Civil religion",
        "F. Jeremiad / \"Christianity under attack\"",
        "G. Ethno-cultural \"real American\" undertones",
        "H. Strongman / authoritarian affinity",
    ]
    # Map variants → canonical by first few chars
    def canon_of(marker: str) -> str:
        prefix = marker.strip()[:2]  # "A.", "B.", etc.
        for c in canonical:
            if c.startswith(prefix):
                return c
        return marker

    header_cells = "".join(f'<th class="pastor-header">{esc(f["meta"]["preacher"].split()[-1])}</th>' for f in findings)
    rows_html = []
    for c in canonical:
        cells = []
        for f in findings:
            status_text = "—"
            for m in f.get("cn_markers", []):
                if canon_of(m.get("marker", "")) == c:
                    status_text = m.get("status", "—")
                    break
            cls = "status-" + normalize_cn_status(status_text)
            cells.append(f'<td class="{cls}">{esc(status_text)}</td>')
        rows_html.append(f"<tr><td>{esc(c)}</td>{''.join(cells)}</tr>")
    return (
        '<table class="cn-matrix">'
        f"<thead><tr><th>CN Marker</th>{header_cells}</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>"
    )


def render_facts_summary(findings: list[dict]) -> str:
    # Aggregate verdict distribution across all sermons
    buckets = {}
    per_pastor_lines = []
    for f in findings:
        counts = {}
        for fc in f.get("factual_claims", []):
            v = fc.get("verdict", "unsupported").lower()
            vclass = VERDICT_CLASS.get(v, "unsupported")
            counts[vclass] = counts.get(vclass, 0) + 1
            buckets[vclass] = buckets.get(vclass, 0) + 1
        # Render per-pastor line
        total = sum(counts.values())
        bars = []
        if total > 0:
            for cls in ("supported", "partial", "contested", "misleading", "unsupported", "false"):
                n = counts.get(cls, 0)
                if n > 0:
                    width = (n / total) * 100
                    label = cls.replace("partial", "partially supported")
                    bars.append(f'<span class="verdict-badge verdict-{cls}" title="{label}: {n}">{n}</span>')
        per_pastor_lines.append(
            f'<div style="margin:.3rem 0;">'
            f'<strong>{esc(f["meta"]["preacher"])}</strong> ({total} claims): '
            f'{" ".join(bars)}'
            f"</div>"
        )

    total = sum(buckets.values())
    aggregate_html = "<div><strong>Aggregate distribution ({} claims):</strong></div>".format(total)
    for cls in ("supported", "partial", "contested", "misleading", "unsupported", "false"):
        n = buckets.get(cls, 0)
        if n == 0:
            continue
        width = (n / total) * 100 if total else 0
        label = {
            "supported": "Supported",
            "partial": "Partially supported",
            "contested": "Contested",
            "misleading": "Misleading",
            "unsupported": "Unsupported",
            "false": "False",
        }[cls]
        aggregate_html += (
            f'<div class="facts-bars">'
            f'<div>{esc(label)}</div>'
            f'<div>{n}</div>'
            f'<div><div class="bar {cls}" style="width: {width:.1f}%;"></div></div>'
            f'</div>'
        )

    return (
        '<div class="facts-summary">'
        f"{aggregate_html}"
        '<div style="margin-top:1rem;">'
        "<strong>Per pastor:</strong>"
        f'{"".join(per_pastor_lines)}'
        "</div>"
        "</div>"
    )


def render_other_axis2_matrix(findings: list[dict]) -> str:
    rubrics = ["Anti-LGBTQ framing", "Misogynistic framing", "Anti-Jewish framing", "Anti-Muslim framing"]
    header_cells = "".join(f'<th class="pastor-header">{esc(f["meta"]["preacher"].split()[-1])}</th>' for f in findings)
    rows_html = []
    for r in rubrics:
        cells = []
        for f in findings:
            status_text = "—"
            for ox in f.get("other_axis2_rubrics", []):
                ox_rubric = ox.get("rubric", "")
                if r.split()[0].lower() in ox_rubric.lower():
                    status_text = ox.get("status", "—")
                    break
            cls = "status-" + normalize_cn_status(status_text)
            cells.append(f'<td class="{cls}">{esc(status_text)}</td>')
        rows_html.append(f"<tr><td>{esc(r)}</td>{''.join(cells)}</tr>")
    return (
        '<table class="cn-matrix">'
        f"<thead><tr><th>Sub-rubric</th>{header_cells}</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>"
    )


def build_html(findings: list[dict]) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    hero = render_hero(findings)
    matrix = render_scorecard_matrix(findings)
    axis_sections = "\n".join(
        render_axis_section(findings, key, label) for key, label in [
            ("axis_1", "Axis 1 — Fidelity to Jesus's Teachings"),
            ("axis_2", "Axis 2 — Identifiable Biases / Harmful Rhetoric"),
            ("axis_3", "Axis 3 — Factual Claims & Evidence"),
            ("axis_4", "Axis 4 — Whole-Bible Engagement"),
        ]
    )
    cn_matrix = render_cn_matrix(findings)
    other_matrix = render_other_axis2_matrix(findings)
    facts_summary = render_facts_summary(findings)

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>whosaid — Sermon Audit Comparison</title>
<style>{CSS}</style>
</head><body>
<div style="font-size:.75rem; color: var(--c-muted); letter-spacing:.1em; text-transform: uppercase;">Cross-Sermon Comparison</div>
<h1>whosaid — Sermon Audit Comparison</h1>
{hero}

<h2>Scorecard Matrix</h2>
{matrix}

<h2>Axis-by-Axis Comparison</h2>
{axis_sections}

<h2>Christian Nationalism Markers Across Sermons</h2>
{cn_matrix}

<h2>Other Axis-2 Sub-rubrics</h2>
{other_matrix}

<h2>Factual-Claim Verdict Distribution</h2>
{facts_summary}

<footer>
<h3>About this comparison</h3>
<p>Each sermon was audited using the whosaid four-axis methodology (see any individual report's footer for methodology details). Verdicts are for the specific sermon analyzed — a single sermon per pastor is a snapshot, not a characterization of the pastor or church.</p>
<p>Generated {esc(generated_at)} from {len(findings)} findings JSON files.</p>
</footer>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("findings", nargs="+", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    findings = load_findings(args.findings)
    out = build_html(findings)
    args.output.write_text(out, encoding="utf-8")
    print(f"Wrote {args.output} ({len(out):,} chars, {len(findings)} sermons)")


if __name__ == "__main__":
    main()
