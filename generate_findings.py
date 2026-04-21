#!/usr/bin/env python3
"""Generate a findings JSON for a sermon transcript via `claude -p`.

Reads:
  - prompts/findings_system_prompt.md
  - prompts/example_howerton_findings.json (few-shot example referenced in the prompt)
  - prompts/findings_schema.json
  - a cleaned transcript (text with [HH:MM:SS] markers)

Writes findings/<slug>.json.

Requires the `claude` CLI (Claude Code) in PATH.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PROMPTS = ROOT / "prompts"
DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_MAX_BUDGET = 3.00


def build_user_prompt(meta: dict, transcript: str, example_findings_path: Path) -> str:
    example_json = example_findings_path.read_text(encoding="utf-8")
    return f"""Here is the reference exemplar findings JSON for a previously analyzed sermon. Match its depth, contrast density, severity calibration, and formatting conventions:

<exemplar-findings>
{example_json}
</exemplar-findings>

Now analyze the following new sermon. Produce a single JSON object (no prose wrapper, no markdown fences) conforming to the schema. Use the exemplar's structure as your guide, but do not copy its content — the findings must reflect THIS sermon's actual content.

Sermon metadata:
<metadata>
{json.dumps(meta, indent=2)}
</metadata>

Sermon transcript (timestamps in [HH:MM:SS] at the start of each paragraph):
<transcript>
{transcript}
</transcript>

Produce the findings JSON now. Remember:
- Evidence over prose — every flagged finding MUST include direct quotes
- Include Jesus's OT citations (with provenance markers) in Axis 1 & 4 Jesus panels
- Fair audit — include tenets_affirmed and counter_signals
- If you cannot verify a factual claim from your own knowledge, use verdict "needs verification" and note what would need to be checked; do not fabricate sources
- Match exemplar depth: at minimum 3 Axis 1 findings, 2 Axis 4 findings, 2 factual claims, 8 CN marker rows
- Output only the JSON object, starting with `{{` and ending with `}}`
"""


def slugify(pastor: str, title: str, upload_date: str) -> str:
    preacher_slug = re.sub(r"[^a-z0-9]+", "_", pastor.lower()).strip("_")
    title_slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:40]
    date = upload_date.replace("-", "")
    return f"{date}_{preacher_slug}_{title_slug}"


def extract_json_object(raw: str) -> dict:
    """Claude Code's --output-format json wraps the schema-validated output in `structured_output`."""
    wrapper = json.loads(raw)
    if wrapper.get("is_error"):
        raise ValueError(f"Claude returned an error: {wrapper.get('result', raw)[:500]}")

    # Preferred: --json-schema validated output is in structured_output
    so = wrapper.get("structured_output")
    if isinstance(so, dict):
        return so

    # Fallback: try to extract JSON from the result text
    inner = wrapper.get("result", "")
    inner = inner.strip()
    if inner.startswith("```"):
        inner = re.sub(r"^```[a-z]*\n", "", inner)
        inner = re.sub(r"\n```\s*$", "", inner)
    start = inner.find("{")
    end = inner.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No structured_output and no JSON found in result")
    return json.loads(inner[start:end + 1])


def call_claude(
    system_prompt: str,
    user_prompt: str,
    schema_path: Path,
    model: str,
    max_budget: float,
) -> str:
    cmd = [
        "claude",
        "-p",
        user_prompt,
        "--model", model,
        "--system-prompt", system_prompt,
        "--output-format", "json",
        "--max-budget-usd", str(max_budget),
        "--tools", "",  # no tools; pure text in/out
        "--json-schema", schema_path.read_text(encoding="utf-8"),
    ]
    print(f"→ claude -p (model={model}, budget=${max_budget}) …", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise RuntimeError(f"claude exited {result.returncode}")
    return result.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", type=Path, required=True)
    ap.add_argument("--youtube-id", required=True)
    ap.add_argument("--preacher", required=True)
    ap.add_argument("--church", required=True)
    ap.add_argument("--sermon-title", required=True)
    ap.add_argument("--upload-date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--runtime-seconds", type=int, required=True)
    ap.add_argument("--series", default="")
    ap.add_argument("--preaching-text", default="")
    ap.add_argument("--church-location", default="")
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-budget", type=float, default=DEFAULT_MAX_BUDGET)
    ap.add_argument("--gospel-translation", default="ESV")
    args = ap.parse_args()

    transcript = args.transcript.read_text(encoding="utf-8")
    system_prompt = (PROMPTS / "findings_system_prompt.md").read_text(encoding="utf-8")
    schema_path = PROMPTS / "findings_schema.json"
    example_path = PROMPTS / "example_howerton_findings.json"

    slug = slugify(args.preacher, args.sermon_title, args.upload_date)
    output = args.output or ROOT / "findings" / f"{slug}.json"
    output.parent.mkdir(parents=True, exist_ok=True)

    meta = {
        "sermon_title": args.sermon_title,
        "preacher": args.preacher,
        "church": args.church,
        "church_location": args.church_location,
        "series": args.series,
        "preaching_text": args.preaching_text,
        "youtube_id": args.youtube_id,
        "upload_date": args.upload_date,
        "runtime_seconds": args.runtime_seconds,
        "transcript_path": str(args.transcript.relative_to(ROOT) if args.transcript.is_absolute() else args.transcript),
        "gospel_translation": args.gospel_translation,
    }

    user_prompt = build_user_prompt(meta, transcript, example_path)

    print(f"Analyzing {args.preacher} — {args.sermon_title}", file=sys.stderr)
    print(f"Transcript: {len(transcript):,} chars; user prompt: {len(user_prompt):,} chars",
          file=sys.stderr)

    raw = call_claude(system_prompt, user_prompt, schema_path, args.model, args.max_budget)

    try:
        parsed = extract_json_object(raw)
    except (ValueError, json.JSONDecodeError) as e:
        debug_path = output.with_suffix(".raw.txt")
        debug_path.write_text(raw, encoding="utf-8")
        sys.exit(f"Failed to parse JSON: {e}. Raw response saved to {debug_path}")

    # Ensure the meta matches what the caller specified (model may echo example)
    parsed["meta"] = meta

    output.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {output}", file=sys.stderr)


if __name__ == "__main__":
    main()
