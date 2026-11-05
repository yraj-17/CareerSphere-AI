"""Safely mark verified non-production user records without deleting them.

Usage (dry-run by default):
    python -m scripts.mark_user_account_flag --kind test --user-id <uuid>
    python -m scripts.mark_user_account_flag --kind test --user-id <uuid> --apply

The command requires explicit user IDs so it cannot classify legitimate
accounts from names, usernames, or email patterns.
"""
from __future__ import annotations

import argparse

from app.db.models import User
from app.db.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", action="append", required=True, help="Verified user ID to mark; repeatable")
    parser.add_argument("--kind", choices=("test", "demo", "system"), required=True)
    parser.add_argument("--apply", action="store_true", help="Persist the marker; otherwise only show the matches")
    args = parser.parse_args()

    field = f"is_{args.kind}_account"
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.id.in_(args.user_id)).order_by(User.id.asc()).all()
        found = {user.id for user in users}
        for user in users:
            print(f"{user.id}\t{user.username}\t{user.email}\t{field}={getattr(user, field)}")
        missing = sorted(set(args.user_id) - found)
        for user_id in missing:
            print(f"NOT FOUND\t{user_id}")

        if not args.apply:
            print("Dry run only. Re-run with --apply after verifying ownership and purpose.")
            return

        for user in users:
            setattr(user, field, True)
        db.commit()
        print(f"Marked {len(users)} user(s) as {args.kind} account(s). No rows were deleted.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
