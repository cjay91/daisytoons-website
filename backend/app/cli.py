"""Command-line tasks. Run with: python -m app.cli <command>"""

import argparse
import getpass
import os
import sys
from pathlib import Path

from app.config import get_settings
from app.db import SessionLocal
from app.errors import AppError
from app.importer import ImportFailed, import_products
from app.models import Staff
from app.services.accounts import create_first_admin, normalize_email
from app.services.orders import release_expired_orders
from app.services.two_factor import clear as clear_two_factor
from app.storage import S3Storage, get_storage


def _create_admin(args: argparse.Namespace) -> int:
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password: ")
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        try:
            staff = create_first_admin(db, email=args.email, password=password, full_name=args.name)
        except AppError as exc:
            print(exc.message, file=sys.stderr)
            return 1
    print(f"Created admin {staff.email} (id {staff.id}).")
    return 0


def _init_storage(_: argparse.Namespace) -> int:
    storage = S3Storage(get_settings())
    created = storage.ensure_bucket()
    print(f"Bucket {storage.bucket} {'created' if created else 'already exists'}.")
    return 0


def _import_products(args: argparse.Namespace) -> int:
    with SessionLocal() as db:
        try:
            summary = import_products(
                db, get_storage(), args.csv, args.images, dry_run=args.dry_run
            )
        except ImportFailed as exc:
            print("Nothing was imported. Fix these and try again:", file=sys.stderr)
            for error in exc.errors:
                print(f"  {error}", file=sys.stderr)
            return 1
    prefix = "Dry run, nothing saved. Would have: " if args.dry_run else ""
    print(
        f"{prefix}{len(summary.created)} created, {len(summary.updated)} updated, "
        f"{len(summary.unchanged)} unchanged; {summary.stock_changes} stock changes logged; "
        f"{summary.images_uploaded} images uploaded."
    )
    return 0


def _release_expired_orders(_: argparse.Namespace) -> int:
    with SessionLocal() as db:
        count = release_expired_orders(db)
    print(f"Released {count} expired orders.")
    return 0


def _reset_two_factor(args: argparse.Namespace) -> int:
    """For an admin who lost their phone and has no other admin to reset it in the console."""
    with SessionLocal() as db:
        staff = db.query(Staff).filter_by(email=normalize_email(args.email)).one_or_none()
        if staff is None:
            print(f"No staff member with email {args.email}.", file=sys.stderr)
            return 1
        clear_two_factor(staff)
        db.commit()
    print(f"Two-step login reset for {args.email}. They set it up again at their next login.")
    return 0


def _run_evals(args: argparse.Namespace) -> int:
    from app.agents.evals import SUITES, run_suite
    from app.agents.model import ClaudeModel
    from app.db import engine

    if args.live and not get_settings().anthropic_api_key:
        print("Set ANTHROPIC_API_KEY to run evals against the real model.", file=sys.stderr)
        return 1
    names = [args.agent] if args.agent else list(SUITES)
    failed = 0
    for name in names:
        scenarios = [s for s in SUITES[name] if s.live or not args.live]
        results = run_suite(engine, scenarios, ClaudeModel if args.live else None)
        for result in results:
            mark = "pass" if result.passed else "FAIL"
            print(f"{mark}  {name}: {result.scenario}  (${result.cost})")
            for failure in result.failures:
                print(f"        {failure}")
        failed += sum(not r.passed for r in results)
    print(f"{failed} failed." if failed else "All passed.")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    create_admin = commands.add_parser("create-admin", help="Create an admin staff account")
    create_admin.add_argument("--email", required=True)
    create_admin.add_argument("--name", required=True)
    create_admin.set_defaults(handler=_create_admin)

    init_storage = commands.add_parser("init-storage", help="Create the image bucket if missing")
    init_storage.set_defaults(handler=_init_storage)

    importer = commands.add_parser("import-products", help="Import products from a CSV file")
    importer.add_argument("csv", type=Path, help="The products CSV file")
    importer.add_argument("--images", type=Path, help="Folder holding the image files")
    importer.add_argument("--dry-run", action="store_true", help="Check without saving")
    importer.set_defaults(handler=_import_products)

    release = commands.add_parser(
        "release-expired-orders", help="Cancel unpaid orders past their time, freeing stock"
    )
    release.set_defaults(handler=_release_expired_orders)

    reset = commands.add_parser(
        "reset-two-factor", help="Turn off a staff member's two-step login so they can redo it"
    )
    reset.add_argument("--email", required=True)
    reset.set_defaults(handler=_reset_two_factor)

    evals = commands.add_parser(
        "run-evals",
        help="Run agent evals (changes nothing: each runs in a rolled-back transaction)",
    )
    evals.add_argument("agent", nargs="?", help="Only this agent's suite")
    evals.add_argument("--live", action="store_true", help="Use the real model, not the script")
    evals.set_defaults(handler=_run_evals)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
