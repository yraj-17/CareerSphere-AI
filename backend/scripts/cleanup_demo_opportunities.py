"""
Remove the fabricated Phase 3.2 demo opportunities and their stale Qdrant vectors.

Dry run by default; pass --apply to delete.

    python -m scripts.cleanup_demo_opportunities          # report only
    python -m scripts.cleanup_demo_opportunities --apply  # delete

PostgreSQL rows are matched by the same two markers as migration 024 (source
'curated' AND an application URL on the fake careersphere.local host), plus rows
left by the test suites (source 'test' / 'phase-3-2-test'). Qdrant points are
removed only when their payload says source == 'curated'. Real provider
listings, users and every other table are never touched.
"""

from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

DEMO_WHERE = (
    "(source = 'curated' AND application_url LIKE 'https://careersphere.local/opportunities/%') "
    "OR source IN ('test', 'phase-3-2-test')"
)


def _cleanup_postgres(apply: bool) -> int:
    with SessionLocal() as db:
        count = db.execute(text(f"SELECT count(*) FROM opportunities WHERE {DEMO_WHERE}")).scalar() or 0
        if apply and count:
            db.execute(text(f"DELETE FROM opportunities WHERE {DEMO_WHERE}"))  # skills cascade
            db.commit()
        return int(count)


def _cleanup_qdrant(apply: bool) -> tuple[int, bool]:
    from qdrant_client.http import models as qmodels

    from app.services.qdrant_service import get_qdrant_client

    client = get_qdrant_client()
    collection = settings.QDRANT_COLLECTION_OPPORTUNITIES
    if not client.collection_exists(collection_name=collection):
        return 0, False
    curated = qmodels.Filter(must=[qmodels.FieldCondition(key="source", match=qmodels.MatchValue(value="curated"))])
    count = client.count(collection_name=collection, count_filter=curated, exact=True).count
    dropped = False
    if apply and count:
        client.delete(collection_name=collection, points_selector=qmodels.FilterSelector(filter=curated))
        if client.count(collection_name=collection, exact=True).count == 0:
            client.delete_collection(collection_name=collection)  # nothing else used it
            dropped = True
    return int(count), dropped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Delete (default is a dry run).")
    args = parser.parse_args()
    verb = "Deleted" if args.apply else "Would delete"

    rows = _cleanup_postgres(args.apply)
    print(f"{verb} {rows} demo/test opportunity row(s) from PostgreSQL.")
    try:
        points, dropped = _cleanup_qdrant(args.apply)
        print(f"{verb} {points} curated vector(s) from Qdrant collection '{settings.QDRANT_COLLECTION_OPPORTUNITIES}'."
              + (" Empty collection removed." if dropped else ""))
    except Exception as exc:
        print(f"Qdrant cleanup skipped: {exc}", file=sys.stderr)
    if not args.apply:
        print("Dry run only. Re-run with --apply to delete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
