"""Simple key management utilities."""

from __future__ import annotations

import argparse
import base64
from pathlib import Path

from crypto.ecc_keywrap import generate_keys
from crypto.key_schedule import generate_master_key


def write_key_file(path: str, key: bytes) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(base64.b64encode(key).decode("ascii"), encoding="utf-8")


def read_key_file(path: str) -> bytes:
    content = Path(path).read_text(encoding="utf-8").strip()
    return base64.b64decode(content.encode("ascii"))


def create_master_key_file(path: str, length: int = 32) -> str:
    key = generate_master_key(length=length)
    write_key_file(path, key)
    return path


def create_x25519_keypair(private_path: str, public_path: str) -> tuple[str, str]:
    generate_keys(private_key_path=private_path, public_key_path=public_path)
    return private_path, public_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Key manager")
    sub = parser.add_subparsers(dest="command", required=True)

    mkey = sub.add_parser("master", help="Create random master key file (base64).")
    mkey.add_argument("--out", required=True, help="Output key file path.")
    mkey.add_argument("--length", type=int, default=32, help="Key length in bytes.")

    ecc = sub.add_parser(
        "x25519",
        aliases=["ecc"],
        help="Create X25519 private/public key pair in PEM format.",
    )
    ecc.add_argument("--private", required=True, help="Private key PEM output path.")
    ecc.add_argument("--public", required=True, help="Public key PEM output path.")
    return parser


def main() -> None:
    parser = _parser()
    args = parser.parse_args()

    if args.command == "master":
        path = create_master_key_file(args.out, length=args.length)
        print(f"Master key written to {path}")
        return

    if args.command in {"x25519", "ecc"}:
        private_path, public_path = create_x25519_keypair(args.private, args.public)
        print(f"Private key: {private_path}")
        print(f"Public key : {public_path}")
        return

    raise RuntimeError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
