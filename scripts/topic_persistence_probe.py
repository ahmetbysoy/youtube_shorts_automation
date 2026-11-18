"""Manual, non-publishing two-run GitHub Contents persistence proof."""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from scripts.topic_history import GitHubContentsStore, finalize_candidate, reserve_candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["reserve", "verify"])
    parser.add_argument("probe_id")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{8,48}", args.probe_id):
        print("[ERROR] probe_id must be 8-48 lowercase letters/digits/hyphens")
        return 2
    try:
        store = GitHubContentsStore(
            os.environ["GITHUB_REPOSITORY"],
            os.environ["GH_TOKEN"],
            ref=os.environ.get("TOPIC_HISTORY_REF", "main"),
        )
        path = ".used_topics.json"
        reservation_id = f"phase3-probe-{args.probe_id}"
        if args.phase == "reserve":
            entry = reserve_candidate(
                f"__PHASE3_PERSISTENCE_PROBE__ {args.probe_id}",
                {"topic": f"__phase3_probe_{args.probe_id}", "topic_source_id": f"phase3_probe_{args.probe_id}"},
                path=Path(path),
                store=store,
                reservation_id=reservation_id,
                run_id=f"probe:{args.probe_id}",
            )
            print(f"[OK] reservation persisted; id={entry['reservation_id']}; run this probe with phase=verify and the same probe_id")
            return 0
        data, _sha = store.get()
        matches = [item for item in data["pending"] if item.get("reservation_id") == reservation_id]
        if len(matches) != 1:
            raise ValueError("Cross-run reservation missing/ambiguous; persistent proof failed.")
        finalize_candidate(reservation_id, commit=False, path=Path(path), store=store)
        print(f"[OK] second Actions run observed and released reservation {reservation_id}; cross-run CAS persistence confirmed")
        return 0
    except Exception as exc:
        print(f"[ERROR] Persistence probe failed ({type(exc).__name__}); no credential values were emitted.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
