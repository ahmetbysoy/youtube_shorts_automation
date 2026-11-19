#!/usr/bin/env python3
"""Faz4E storyboard_report.json -> markdown ozet (GITHUB_STEP_SUMMARY icin)."""
import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("kullanim: phase4e_summary.py <storyboard_report.json>", file=sys.stderr)
        return 2
    r = json.loads(Path(sys.argv[1]).read_text("utf8"))
    ozet = {
        "status": r.get("status"),
        "visual_verification": "not_performed",  # metadata kontrolden asla verified yazma
        "scenes": [
            {"scene_id": s["scene_id"], "provider": s["selected_provider"], "media_id": s["selected_media_id"],
             "license_name": (s.get("license") or {}).get("name"),
             "license_verified": (s.get("license") or {}).get("verified"),
             "attribution_present": bool(s.get("attribution")),
             "duration": s.get("duration"), "resolution": s.get("resolution"),
             "source_url": s.get("source_url"),
             "download_status": s.get("download_status")}
            for s in r.get("scenes", [])
        ]
    }
    print("```json")
    print(json.dumps(ozet, indent=2, ensure_ascii=False))
    print("```")
    return 0


if __name__ == "__main__":
    sys.exit(main())
