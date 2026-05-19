#!/usr/bin/env python3
"""Encrypt booking-site credentials into the blob the API expects.

The /api/login and /api/wanted endpoints never take a plaintext PIN — they
take an AES-256-GCM blob produced with the same TSA_SHARED_SECRET the API
runs with. This script produces that blob.

Resolution order for the shared secret:
  1. --secret PINVALUE
  2. $TSA_SHARED_SECRET
  3. TSA_SHARED_SECRET=... in ./.env or ../.env (repo-root .env)

Usage (from repo root or from api/):
  python3 api/encrypt_credentials.py                    # prompts for both
  python3 api/encrypt_credentials.py -u 12345           # prompts for PIN
  python3 api/encrypt_credentials.py -u 12345 -p 6789
  python3 api/encrypt_credentials.py -u 12345 --curl    # also print curl JSON

Tip: piping the PIN avoids it landing in shell history:
  python3 api/encrypt_credentials.py -u 12345 --pin-stdin <<<'6789'
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

# Make `app` importable whether run from repo root or from api/.
_API_DIR = Path(__file__).resolve().parent
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))


def _secret_from_dotenv() -> str | None:
    """Look for TSA_SHARED_SECRET in ./.env then ../.env."""
    for env_path in (_API_DIR / ".env", _API_DIR.parent / ".env"):
        if not env_path.is_file():
            continue
        for raw in env_path.read_text().splitlines():
            line = raw.strip()
            if line.startswith("TSA_SHARED_SECRET="):
                return line.split("=", 1)[1].strip().strip("'\"")
    return None


def resolve_secret(cli_secret: str | None) -> str:
    secret = cli_secret or os.environ.get("TSA_SHARED_SECRET") or _secret_from_dotenv()
    if not secret:
        sys.exit(
            "error: shared secret not found. Pass --secret, set "
            "TSA_SHARED_SECRET, or add it to .env (repo root)."
        )
    return secret


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Encrypt member ID + PIN into the API credentials blob."
    )
    parser.add_argument("-u", "--member-id", help="Booking-site member ID")
    parser.add_argument("-p", "--pin", help="Booking-site PIN (omit to be prompted)")
    parser.add_argument(
        "--pin-stdin",
        action="store_true",
        help="Read the PIN from stdin instead of prompting",
    )
    parser.add_argument(
        "--secret",
        help="TSA_SHARED_SECRET (else env, else .env)",
    )
    parser.add_argument(
        "--curl",
        action="store_true",
        help="Also print a ready-to-use JSON body for /api/login",
    )
    args = parser.parse_args()

    secret = resolve_secret(args.secret)

    member_id = args.member_id or input("Member ID: ").strip()
    if not member_id:
        sys.exit("error: member ID is required")

    if args.pin:
        pin = args.pin
    elif args.pin_stdin:
        pin = sys.stdin.readline().rstrip("\n")
    else:
        pin = getpass.getpass("PIN: ")
    if not pin:
        sys.exit("error: PIN is required")

    try:
        from app.services.encryption import EncryptionService
    except ModuleNotFoundError as exc:  # pragma: no cover - env guidance
        sys.exit(
            f"error: could not import the app ({exc}). Run with the API "
            "virtualenv, e.g. `api/.venv/bin/python api/encrypt_credentials.py`."
        )

    blob = EncryptionService(secret).encrypt_credentials(member_id, pin)
    print(blob)

    if args.curl:
        print()
        print("# POST body for /api/login (and the credentials field for /api/wanted):")
        print(f'{{"credentials": "{blob}"}}')


if __name__ == "__main__":
    main()
