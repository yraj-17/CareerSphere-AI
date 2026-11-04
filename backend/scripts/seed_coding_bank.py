"""
Seed the curated coding problem bank and verify it on the real Judge0 service.

Usage (from backend/):

    python -m scripts.seed_coding_bank              # validate + seed (idempotent)
    python -m scripts.seed_coding_bank --verify     # seed, then verify unverified problems on Judge0
    python -m scripts.seed_coding_bank --verify --force --only dsa-bracket-validator

Seeding is keyed by slug with a content hash: re-running it changes nothing unless a
problem's content changed, in which case that problem is updated and must be verified
again before interviews can use it. Verification needs JUDGE0_API_URL / JUDGE0_AUTH_TOKEN
(for local development, through the SSH tunnel). Hidden tests are never printed.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.db.session import SessionLocal  # noqa: E402
from app.services import coding_bank_service as bank  # noqa: E402


def _print_verification(slug: str, result: dict) -> bool:
    if result.get("error"):
        print(f"  FAIL {slug}: {result['error']}")
        return False
    marker = "PASS" if result.get("verified") else "FAIL"
    suffix = " (already verified; use --force to re-run)" if result.get("skipped") else ""
    print(f"  {marker} {slug}{suffix}")
    for language, r in (result.get("languages") or {}).items():
        print(f"      reference {language:<10} {r['verdict']:<22} {r['passed']}/{r['total']}  max {r['max_time']}s  {r['label']}")
    for w in result.get("wrong_solutions") or []:
        print(f"      wrong     {w['language']:<10} {w['verdict']:<22} {w['passed']}/{w['total']}  {'rejected' if w['detected'] else 'NOT REJECTED'} - {w['note']}")
    for language, st in (result.get("starters") or {}).items():
        print(f"      starter   {language:<10} {st['verdict']:<22} {'ok' if st['ok'] else 'PROBLEM'}")
    return bool(result.get("verified"))


async def _main(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        summary = bank.seed_bank(db)
        print(f"Seeded problem bank: {len(summary['created'])} created, {len(summary['updated'])} updated, "
              f"{len(summary['unchanged'])} unchanged, {len(summary['deactivated'])} deactivated.")
        for key in ("created", "updated", "deactivated"):
            for slug in summary[key]:
                print(f"  {key}: {slug}")
        if not args.verify:
            return 0
        only = set(args.only) if args.only else None
        print("Verifying on Judge0 (references must pass, wrong solutions must be rejected, starters must run)...")
        report = await bank.verify_bank(db, only=only, force=args.force)
        ok = [_print_verification(slug, result) for slug, result in report.items()]
        print(f"Verified: {sum(ok)}/{len(ok)}")
        return 0 if all(ok) else 1
    finally:
        db.close()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--verify", action="store_true", help="verify problems on Judge0 after seeding")
    parser.add_argument("--force", action="store_true", help="re-verify problems that are already verified")
    parser.add_argument("--only", nargs="*", help="limit verification to these slugs")
    sys.exit(asyncio.run(_main(parser.parse_args())))


if __name__ == "__main__":
    main()
