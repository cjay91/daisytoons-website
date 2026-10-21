"""Command-line tasks. Run with: python -m app.cli <command>"""

import argparse
import getpass
import os
import sys

from app.db import SessionLocal
from app.errors import AppError
from app.services.accounts import create_first_admin


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    create_admin = commands.add_parser("create-admin", help="Create an admin staff account")
    create_admin.add_argument("--email", required=True)
    create_admin.add_argument("--name", required=True)
    create_admin.set_defaults(handler=_create_admin)
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
