"""CLI entrypoint for hybrid image encryption/decryption."""

from __future__ import annotations

import argparse
import json

from pipeline.decrypt import decrypt_image_adaptive
from pipeline.encrypt import encrypt_image_adaptive


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hybrid adaptive image encryption CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    enc = sub.add_parser("encrypt", help="Encrypt an image.")
    enc.add_argument("--input", required=True, help="Input image path.")
    enc.add_argument("--output", required=True, help="Encrypted output path.")
    enc.add_argument("--metadata", required=True, help="Metadata output path.")
    enc.add_argument("--passphrase", help="Passphrase used for key derivation.")
    enc.add_argument(
        "--recipient-public-key",
        help="Optional recipient X25519 public key PEM path for ephemeral key exchange mode.",
    )
    enc.add_argument(
        "--threat",
        default="balanced",
        choices=["speed", "balanced", "hardened"],
        help="Threat profile used by adaptive selector.",
    )
    enc.add_argument(
        "--profile",
        default="auto",
        choices=["auto", "lite", "standard", "max"],
        help="Force a specific profile or keep auto selection.",
    )
    enc.add_argument(
        "--publication-goal",
        default="Strong final-year + Scopus",
        choices=[
            "Resume booster conference",
            "Strong final-year + Scopus",
            "Serious cryptography-track prep",
        ],
        help="Research positioning label stored in metadata.",
    )
    enc.add_argument(
        "--adversary",
        action="append",
        choices=[
            "Chosen-plaintext attacker",
            "Known-plaintext attacker",
            "Ciphertext-only attacker",
            "Replay attacker",
        ],
        help="Adversary assumptions to persist in metadata. Repeat flag for multiple values.",
    )
    enc.add_argument(
        "--relaxed-claims",
        action="store_true",
        help="Disable strict claims mode in metadata context.",
    )

    dec = sub.add_parser("decrypt", help="Decrypt an encrypted image.")
    dec.add_argument("--input", required=True, help="Encrypted input path.")
    dec.add_argument("--output", required=True, help="Recovered image output path.")
    dec.add_argument("--metadata", required=True, help="Metadata file path.")
    dec.add_argument("--passphrase", help="Passphrase used during encryption.")
    dec.add_argument(
        "--recipient-private-key",
        help="Recipient X25519 private key PEM path when metadata key exchange mode uses x25519.",
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "encrypt":
        forced_profile = None if args.profile == "auto" else args.profile
        if not args.passphrase and not args.recipient_public_key:
            raise ValueError("Provide --passphrase and/or --recipient-public-key for encryption.")
        security_context = {
            "publication_goal": args.publication_goal,
            "adversary_models": args.adversary
            or [
                "Chosen-plaintext attacker",
                "Known-plaintext attacker",
                "Ciphertext-only attacker",
            ],
            "strict_claims_mode": not args.relaxed_claims,
            "cli_key_exchange_inputs": {
                "has_passphrase": bool(args.passphrase),
                "has_recipient_public_key": bool(args.recipient_public_key),
            },
        }
        metadata = encrypt_image_adaptive(
            input_image_path=args.input,
            encrypted_output_path=args.output,
            metadata_output_path=args.metadata,
            passphrase=args.passphrase,
            threat_level=args.threat,
            forced_profile=forced_profile,
            security_context=security_context,
            recipient_public_key_path=args.recipient_public_key,
        )
        print(json.dumps(metadata, indent=2))
        return

    if args.command == "decrypt":
        metadata = decrypt_image_adaptive(
            encrypted_input_path=args.input,
            output_image_path=args.output,
            metadata_path=args.metadata,
            passphrase=args.passphrase,
            recipient_private_key_path=args.recipient_private_key,
        )
        print(
            json.dumps(
                {
                    "status": "ok",
                    "classification": metadata.get("classification", {}),
                    "profile": metadata.get("profile", {}),
                },
                indent=2,
            )
        )
        return

    raise RuntimeError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
