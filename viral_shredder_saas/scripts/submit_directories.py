"""Autonomous directory submission script.

Runs the whole marketing submission pass with no human interaction:

    python scripts/submit_directories.py              # live run
    python scripts/submit_directories.py --dry-run    # build payloads, no network
    python scripts/submit_directories.py --only "Toolify.ai,Futurepedia"

Each submission is written to submissions.jsonl and to the app's database, so a
run can be re-run safely and audited later from /marketing in the dashboard.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Make the package importable when the script is run from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import database as db  # noqa: E402
from app import marketing  # noqa: E402

log = logging.getLogger("viral_shredder.submit")


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit Viral Shredder to directories.")
    parser.add_argument("--dry-run", action="store_true",
                        help="prepare every payload but skip the network calls")
    parser.add_argument("--only", default="",
                        help="comma-separated directory names to limit the run to")
    parser.add_argument("--json", action="store_true",
                        help="print the result summary as JSON")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    db.init_db()

    only = [p.strip() for p in args.only.split(",") if p.strip()]
    if args.dry_run:
        log.info("DRY RUN - no submissions will be sent")

    log.info("submitting %s to %d directories", marketing.default_product()["name"],
             len(marketing.load_directories()))

    results = marketing.run_submission(dry_run=args.dry_run, only=only or None)
    summary = marketing.summary(results)

    for r in results:
        log.info("  %-28s %-8s %s", r.directory, r.status.upper(),
                 r.http_code or r.detail[:60])

    log.info("done: %s", json.dumps(summary))
    if args.json:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
