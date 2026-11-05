"""
Synchronise real job listings from the configured providers.

    python -m scripts.sync_jobs                     # every configured provider
    python -m scripts.sync_jobs --provider lever    # one provider
    python -m scripts.sync_jobs --status            # print provider status only

The API also syncs automatically (JOB_SYNC_ENABLED / JOB_SYNC_INTERVAL_MINUTES)
and admins can trigger POST /api/career-matching/admin/sync.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.db.session import SessionLocal  # noqa: E402
from app.services.job_sync_service import PROVIDER_KEYS, provider_status, run_full_sync  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronise real job listings.")
    parser.add_argument("--provider", choices=PROVIDER_KEYS, default=None)
    parser.add_argument("--status", action="store_true", help="Only print provider status.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    if not args.status:
        summary = run_full_sync(trigger="cli", only=args.provider)
        if not summary.started:
            print(summary.reason)
            return 1
        if summary.reason:
            print(summary.reason)
        print(f"\n{'source':<55} {'status':<8} {'fetched':>7} {'kept':>5} {'new':>5} {'upd':>5} {'gone':>5}")
        for r in summary.sources:
            name = f"{r.provider}:{r.source_board}"
            print(f"{name:<55} {r.status:<8} {r.fetched:>7} {r.kept:>5} {r.inserted:>5} {r.updated:>5} {r.deactivated:>5}"
                  + (f"  {r.error}" if r.error else ""))
        print(f"Expiry: {summary.expiry}")

    with SessionLocal() as db:
        print(json.dumps(provider_status(db), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
