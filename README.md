# whosaid

A structured audit of modern American sermons measured against four independent axes:

1. **Fidelity to Jesus's Teachings** — the pastor's claims compared against Jesus's direct words in the four Gospels, including OT passages Jesus explicitly cited or interpreted.
2. **Identifiable Biases / Harmful Rhetoric** — Christian nationalism markers (Whitehead & Perry; Du Mez; Alberta), plus anti-Muslim, anti-LGBTQ, misogynistic, and anti-Jewish framings.
3. **Factual Claims & Evidence Check** — empirical claims extracted from the sermon compared against independent sources.
4. **Whole-Bible Engagement** — cherry-picking and unacknowledged canonical tension; three-panel contrast of Pastor | Jesus | Wider Bible.

Published review site: [whosaid sermon audits](https://chicks.github.io/whosaid/)

## Pipeline

```
YouTube URL
  → yt-dlp (auto-captions)
    → clean_vtt.py (plain timestamped transcript)
      → generate_findings.py (Claude Opus 4.7 with --json-schema)
        → report_generator/generate_report.py (per-sermon HTML)
        → report_generator/generate_comparison.py (cross-sermon HTML)
        → report_generator/generate_calibration.py (focused side-by-side)
          → to_pdf.py (PDF via headless Chrome)
```

One command end-to-end:

```bash
python3 run_sermon_audit.py \
  --url "https://www.youtube.com/watch?v=<video_id>" \
  --preacher "Pastor Name" \
  --church "Church Name" \
  --church-location "City, ST"
```

Per sermon: ~$1 and ~5 minutes of Claude Opus 4.7 time.

## Directory layout

- `docs/` — GitHub Pages root (landing page + all rendered HTML reports + PDFs)
- `findings/` — structured findings JSONs (source of truth for the audits)
- `findings/_non_endtimes/` — earlier non-topical audits
- `transcripts/` — cleaned transcripts (timestamped paragraphs)
- `prompts/` — the system prompt, JSON schema, and few-shot exemplar used by `generate_findings.py`
- `report_generator/` — HTML generators
- Scripts at root: `run_sermon_audit.py`, `clean_vtt.py`, `generate_findings.py`, `augment_reach.py`, `to_pdf.py`, `serve.py`

## Methodology transparency

The `prompts/` directory contains the full system prompt (`findings_system_prompt.md`), the JSON schema used for structured output validation (`findings_schema.json`), and the hand-authored exemplar report (`example_howerton_findings.json`) that every subsequent audit was calibrated against. Every finding in every report is traceable to these inputs plus the underlying transcript.

## License

Code: MIT.
Reports and methodology: CC-BY 4.0.
Quoted sermon content: quoted under fair use for commentary and criticism (17 U.S.C. § 107).

## Contact

charles@reliable.cx
