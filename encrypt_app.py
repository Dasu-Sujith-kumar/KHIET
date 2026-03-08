"""Streamlit UI for adaptive image encryption."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from pipeline.encrypt import encrypt_image_adaptive


def _save_uploaded_image(uploaded_file: Any) -> str:
    suffix = Path(uploaded_file.name).suffix or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as fh:
        fh.write(uploaded_file.getbuffer())
        return fh.name


def _artifact_paths(stem: str) -> tuple[Path, Path]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    encrypted = out_dir / f"{stem}_{ts}.enc"
    metadata = out_dir / f"{stem}_{ts}.meta.json"
    return encrypted, metadata


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
        passphrase = st.text_input("Passphrase", type="password", help="Optional when X25519-only mode is used.")
        recipient_public_key_pem_text = st.text_area(
            "Recipient X25519 public key PEM",
            help="Required for X25519-only and Hybrid modes.",
            height=140,
        )
        threat_level = st.selectbox("Threat level", ["speed", "balanced", "hardened"], index=1)
        mode = st.radio("Profile mode", ["Auto", "Force profile"], index=0)
        forced_profile = None
        if mode == "Force profile":
            forced_profile = st.selectbox("Forced profile", ["lite", "standard", "max"], index=1)
        publication_goal = st.selectbox(
            "Publication goal",
            [
                "Resume booster conference",
                "Strong final-year + Scopus",
                "Serious cryptography-track prep",
            ],
            index=1,
        )
        adversary_models = st.multiselect(
            "Adversary assumptions",
            [
                "Chosen-plaintext attacker",
                "Known-plaintext attacker",
                "Ciphertext-only attacker",
                "Replay attacker",
            ],
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

    recipient_public_key_pem = (
        recipient_public_key_pem_text.encode("utf-8")
        if recipient_public_key_pem_text.strip()
        else None
    )
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
                "publication_goal": publication_goal,
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

            cipher_bytes = encrypted_path.read_bytes()
            metadata_text = metadata_path.read_text(encoding="utf-8")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Sensitivity", metadata["classification"]["label"])
            c2.metric("Profile", metadata["profile"]["name"])
            c3.metric("Cipher bytes", f"{len(cipher_bytes):,}")
            c4.metric("Nonce strategy", "K2-derived")
            st.caption(f"Key exchange mode: {metadata.get('key_exchange', {}).get('mode', 'unknown')}")

            st.success("Encryption completed.")
            st.info(
                "Security mapping: confidentiality + integrity rely on AES-GCM; metadata integrity relies on HMAC (K4)."
            )
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

        except Exception as exc:  # noqa: BLE001
            st.error(f"Encryption failed: {exc}")

    if uploaded is not None and not ready:
        st.info("Provide required key material for the selected key exchange mode.")


if __name__ == "__main__":
    main()
