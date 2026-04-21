#!/usr/bin/env python3
"""Augment existing findings JSONs with reach data:

- video view_count (from yt-dlp --dump-json)
- channel subscriber_count (from yt-dlp on the channel)
- estimated weekly congregation (static table, cited sources)
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
import sys

# Weekly-attendance / membership estimates, with sources.
# These are public figures and approximate. Numbers vary by source and year.
CONGREGATION_ESTIMATES = {
    "Lakepointe Church": {
        "weekly_attendance_est": 26000,
        "source": "Outreach Magazine Largest Churches list, 2024; pastor cited 53,000 for Easter 2026 weekend",
    },
    "The Potter's House": {
        "weekly_attendance_est": 30000,
        "source": "Church-reported multi-campus weekly; Outreach Magazine",
    },
    "Grace Community Church": {
        "weekly_attendance_est": 8000,
        "source": "Hartford Institute for Religion Research megachurch database",
    },
    "First Baptist Dallas": {
        "weekly_attendance_est": 16000,
        "source": "Hartford Institute megachurch database",
    },
    "Elevation Church": {
        "weekly_attendance_est": 28000,
        "source": "Outreach Magazine Largest Churches list (multi-campus)",
    },
    "Christ Church": {
        "weekly_attendance_est": 2000,
        "source": "Church public filings; Moscow-Pullman Daily News reporting. Smaller than megachurches but influential via Canon Press publishing network.",
    },
    "Christ Church (speaking at Pentagon prayer meeting convened by Secretary of War Pete Hegseth)": {
        "weekly_attendance_est": None,
        "audience_context": "Pentagon prayer meeting — audience was senior Department of War staff and invitees. Not a congregation in the usual sense; reach multiplier is institutional/political.",
        "source": "dougwils.com; reporting on the Hegseth-convened Pentagon prayer meetings",
    },
    "Global Vision Bible Church": {
        "weekly_attendance_est": 3500,
        "source": "Reporting by The Tennessean and Religion News Service; Locke's broader social-media reach is much larger than in-person attendance",
    },
    "Cornerstone Church": {
        "weekly_attendance_est": 22000,
        "source": "Hartford Institute megachurch database; Cornerstone self-reported",
    },
    "Calvary Chapel Chino Hills": {
        "weekly_attendance_est": 10000,
        "source": "Hartford Institute megachurch database; recent self-reports from Hibbs's ministry",
    },
    "North Point Community Church": {
        "weekly_attendance_est": 30000,
        "source": "Outreach Magazine Largest Churches list (multi-campus)",
    },
}


def yt_dump(url: str) -> dict:
    try:
        r = subprocess.run(
            ["yt-dlp", "--skip-download", "--dump-json", url],
            capture_output=True, text=True, check=True, timeout=60,
        )
        return json.loads(r.stdout)
    except subprocess.CalledProcessError as e:
        print(f"yt-dlp failed for {url}: {e.stderr[:200]}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"yt-dlp error: {e}", file=sys.stderr)
        return {}


def augment(findings_path: Path) -> None:
    data = json.loads(findings_path.read_text(encoding="utf-8"))
    meta = data["meta"]
    reach = data.get("reach") or {}

    yt_id = meta.get("youtube_id", "")
    # Skip yt-dlp for non-YouTube sources (our placeholder for blog-sourced transcripts)
    is_youtube = len(yt_id) == 11 and all(c.isalnum() or c in "-_" for c in yt_id)
    if is_youtube:
        video = yt_dump(f"https://www.youtube.com/watch?v={yt_id}")
        if video:
            reach["view_count"] = video.get("view_count")
            reach["like_count"] = video.get("like_count")
            reach["channel"] = video.get("channel")
            reach["channel_id"] = video.get("channel_id")
            reach["channel_follower_count"] = video.get("channel_follower_count")
            reach["upload_date"] = video.get("upload_date")
            reach["source"] = "yt-dlp"
    else:
        reach.setdefault("source", "non-YouTube (blog-sourced transcript)")

    # Congregation estimate
    church = meta.get("church", "")
    congreg = CONGREGATION_ESTIMATES.get(church)
    if congreg:
        reach["congregation"] = congreg
    else:
        # Try a prefix match for long church strings
        for key, val in CONGREGATION_ESTIMATES.items():
            if church.startswith(key):
                reach["congregation"] = val
                break

    data["reach"] = reach
    findings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    views = reach.get("view_count")
    subs = reach.get("channel_follower_count")
    cong = reach.get("congregation", {}).get("weekly_attendance_est")
    print(f"{findings_path.name:60s} views={views or '—'} subs={subs or '—'} weekly_est={cong or '—'}",
          file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("findings", nargs="+", type=Path)
    args = ap.parse_args()
    for p in args.findings:
        augment(p)


if __name__ == "__main__":
    main()
