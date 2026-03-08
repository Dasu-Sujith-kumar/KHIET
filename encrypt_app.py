"""Streamlit UI for adaptive image encryption."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import streamlit as st

from crypto.ecc_keywrap import generate_keys
from pipeline.encrypt import encrypt_image_adaptive

ENCRYPT_RESULT_KEY = "encrypt_result"
GENERATED_X25519_KEYPAIR_KEY = "generated_x25519_keypair"


def _save_uploaded_image(uploaded_file: Any) -> str:
    suffix = Path(uploaded_file.name).suffix or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as fh:
        fh.write(uploaded_file.getbuffer())
        return fh.name


def _artifact_paths(stem: str) -> tuple[Path, Path]:
    out_dir = Path("artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    encrypted = out_dir / f"{stem}_encrypted.enc"
    metadata = out_dir / f"{stem}_metadata.json"
    if not encrypted.exists() and not metadata.exists():
        return encrypted, metadata

    counter = 2
    while True:
        encrypted = out_dir / f"{stem}_{counter}_encrypted.enc"
        metadata = out_dir / f"{stem}_{counter}_metadata.json"
        if not encrypted.exists() and not metadata.exists():
            return encrypted, metadata
        counter += 1


def _resolve_pem_input(text_value: str, uploaded_file: Any | None) -> bytes | None:
    if uploaded_file is not None:
        return uploaded_file.getvalue()

    stripped = text_value.strip()
    if not stripped:
        return None

    candidate = Path(stripped)
    if candidate.is_file():
        return candidate.read_bytes()

    return stripped.encode("utf-8")


def _generated_x25519_keypair() -> dict[str, bytes] | None:
    value = st.session_state.get(GENERATED_X25519_KEYPAIR_KEY)
    if not isinstance(value, dict):
        return None
    private_pem = value.get("private_pem")
    public_pem = value.get("public_pem")
    if not isinstance(private_pem, bytes) or not isinstance(public_pem, bytes):
        return None
    return value


def _render_encrypt_result(result: dict[str, Any]) -> None:
    encrypted_path = Path(result["encrypted_path"])
    metadata_path = Path(result["metadata_path"])
    if not encrypted_path.is_file() or not metadata_path.is_file():
        st.session_state.pop(ENCRYPT_RESULT_KEY, None)
        st.warning("Latest encryption artifacts were removed. Encrypt again to regenerate downloads.")
        return

    cipher_bytes = encrypted_path.read_bytes()
    metadata_text = metadata_path.read_text(encoding="utf-8")
    metadata = result["metadata"]

    st.subheader("Latest encryption result")
    if result.get("source_name"):
        st.caption(f"Source image: {result['source_name']}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sensitivity", metadata["classification"]["label"])
    c2.metric("Profile", metadata["profile"]["name"])
    c3.metric("Cipher bytes", f"{len(cipher_bytes):,}")
    c4.metric("Nonce strategy", "K2-derived")
    st.caption(f"Key exchange mode: {metadata.get('key_exchange', {}).get('mode', 'unknown')}")

    st.success("Encryption completed.")
    st.info("Security mapping: confidentiality + integrity rely on AES-GCM; metadata integrity relies on HMAC (K4).")
    st.download_button(
        "Download encrypted bytes",
        data=cipher_bytes,
        file_name=encrypted_path.name,
        mime="application/octet-stream",
    )
    st.download_button(
        "Download metadata JSON",
        data=metadata_text,
        file_name=metadata_path.name,
        mime="application/json",
    )

    with st.expander("Metadata details", expanded=True):
        st.json(json.loads(metadata_text))


def main() -> None:
    st.set_page_config(page_title="Hybrid Encrypt", layout="wide")
    st.title("Adaptive Hybrid Encryption")
    st.caption("Feature update: profile-aware encryption with metadata-driven transparency.")

    with st.sidebar:
        st.subheader("Encryption Settings")
        key_mode = st.selectbox(
            "Key exchange mode",
            ["Passphrase only", "X25519 only", "Hybrid (Passphrase + X25519)"],
            index=0,
        )
        passphrase = ""
        if key_mode != "X25519 only":
            passphrase = st.text_input("Passphrase", type="password")
        recipient_public_key_pem_text = ""
        recipient_public_key_pem_file = None
        if key_mode != "Passphrase only":
            recipient_public_key_pem_text = st.text_area(
                "Recipient X25519 public key PEM",
                help="Paste PEM text or enter a local .pem path. Required for X25519-only and Hybrid modes.",
                height=140,
            )
            recipient_public_key_pem_file = st.file_uploader(
                "Or upload recipient public key (.pem)",
                type=["pem"],
                accept_multiple_files=False,
            )
            st.caption("No key pair yet? Generate one here and download the private key for decryption later.")
            if st.button("Generate random X25519 key pair", use_container_width=True):
                private_pem, public_pem = generate_keys()
                st.session_state[GENERATED_X25519_KEYPAIR_KEY] = {
                    "private_pem": private_pem,
                    "public_pem": public_pem,
                }

            generated_keypair = _generated_x25519_keypair()
            if generated_keypair is not None:
                st.success("Generated X25519 key pair is ready for this session.")
                st.caption("The generated public key is used automatically unless you paste or upload a different public key.")
                st.caption("Download and keep the private key safe. You will need it in the decrypt UI.")
                st.download_button(
                    "Download generated public key",
                    data=generated_keypair["public_pem"],
                    file_name="x25519_public.pem",
                    mime="application/x-pem-file",
                )
                st.download_button(
                    "Download generated private key",
                    data=generated_keypair["private_pem"],
                    file_name="x25519_private.pem",
                    mime="application/x-pem-file",
                )
        threat_level = st.selectbox("Threat level", ["speed", "balanced", "hardened"], index=1)
        mode = st.radio(
            "Profile mode",
            ["Auto", "Force profile"],
            index=0,
            help="Auto uses a heuristic classifier based on image entropy, edge density, and variance. It does not use ArcFace.",
        )
        forced_profile = None
        if mode == "Force profile":
            forced_profile = st.selectbox("Forced profile", ["lite", "standard", "max"], index=1)
        adversary_models = st.multiselect(
            "Adversary assumptions (metadata only)",
            [
                "Chosen-plaintext attacker",
                "Known-plaintext attacker",
                "Ciphertext-only attacker",
                "Replay attacker",
            ],
            help="This is only saved into metadata for documentation. It does not change profile selection or encryption strength.",
            default=[
                "Chosen-plaintext attacker",
                "Known-plaintext attacker",
                "Ciphertext-only attacker",
            ],
        )
        strict_claims_mode = st.checkbox("Strict claims mode", value=True)

    uploaded = st.file_uploader("Upload image", type=["png", "jpg", "jpeg", "bmp", "webp"])
    if uploaded is not None:
        st.image(uploaded, caption="Input preview", use_container_width=True)

    with st.expander("Research design boundaries", expanded=False):
        st.markdown(
            "\n".join(
                [
                    "- Uses standard AES-GCM (no AES internal modifications).",
                    "- Does not claim a custom block cipher.",
                    "- Uses domain-separated key roles (K1..K4).",
                    "- Metadata is authenticated (HMAC) and verified on decrypt.",
                ]
            )
        )

    if not strict_claims_mode:
        st.warning("Strict claims mode disabled. Keep paper claims conservative during write-up.")

    recipient_public_key_pem = _resolve_pem_input(
        recipient_public_key_pem_text,
        recipient_public_key_pem_file,
    )
    generated_keypair = _generated_x25519_keypair()
    if (
        key_mode != "Passphrase only"
        and recipient_public_key_pem is None
        and generated_keypair is not None
    ):
        recipient_public_key_pem = generated_keypair["public_pem"]

    if key_mode == "Passphrase only":
        recipient_public_key_pem = None
    if key_mode == "Passphrase only":
        ready = uploaded is not None and bool(passphrase)
    elif key_mode == "X25519 only":
        ready = uploaded is not None and recipient_public_key_pem is not None
    else:
        ready = uploaded is not None and bool(passphrase) and recipient_public_key_pem is not None

    if st.button("Encrypt", type="primary", disabled=not ready):
        try:
            input_path = _save_uploaded_image(uploaded)
            base_stem = Path(uploaded.name).stem or "image"
            encrypted_path, metadata_path = _artifact_paths(base_stem)
            security_context = {
                "adversary_models": adversary_models,
                "strict_claims_mode": strict_claims_mode,
                "ui_key_exchange_mode": key_mode,
            }

            metadata = encrypt_image_adaptive(
                input_image_path=input_path,
                encrypted_output_path=str(encrypted_path),
                metadata_output_path=str(metadata_path),
                passphrase=passphrase or None,
                threat_level=threat_level,
                forced_profile=forced_profile,
                security_context=security_context,
                recipient_public_key_pem=recipient_public_key_pem,
            )
            st.session_state[ENCRYPT_RESULT_KEY] = {
                "encrypted_path": str(encrypted_path),
                "metadata_path": str(metadata_path),
                "metadata": metadata,
                "source_name": uploaded.name,
            }

        except Exception as exc:  # noqa: BLE001
            st.session_state.pop(ENCRYPT_RESULT_KEY, None)
            st.error(f"Encryption failed: {exc}")

    result = st.session_state.get(ENCRYPT_RESULT_KEY)
    if result is not None:
        _render_encrypt_result(result)

    if uploaded is not None and not ready:
        st.info("Provide required key material for the selected key exchange mode.")


if __name__ == "__main__":
    main()
