"""Streamlit UI for adaptive image decryption."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from pipeline.decrypt import decrypt_image_adaptive


def _write_temp(uploaded_file: Any, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as fh:
        fh.write(uploaded_file.getbuffer())
        return fh.name


def _output_image_path(stem: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{stem}_{ts}.decrypted.png"


def main() -> None:
    st.set_page_config(page_title="Hybrid Decrypt", layout="wide")
    st.title("Adaptive Hybrid Decryption")
    st.caption("Upload encrypted bytes + metadata JSON from the encryption app.")

    passphrase = st.text_input("Passphrase", type="password")
    recipient_private_key_pem_text = st.text_area(
        "Recipient X25519 private key PEM",
        help="Required when metadata key exchange mode is x25519_only or hybrid_passphrase_x25519.",
        height=140,
    )
    encrypted_file = st.file_uploader("Encrypted file (.enc/.bin)", type=["enc", "bin", "dat"])
    metadata_file = st.file_uploader("Metadata JSON", type=["json"])

    recipient_private_key_pem = (
        recipient_private_key_pem_text.encode("utf-8")
        if recipient_private_key_pem_text.strip()
        else None
    )
    ready = encrypted_file is not None and metadata_file is not None
    if st.button("Decrypt", type="primary", disabled=not ready):
        try:
            encrypted_path = _write_temp(encrypted_file, suffix=".enc")
            metadata_path = _write_temp(metadata_file, suffix=".json")
            output_path = _output_image_path(Path(encrypted_file.name).stem or "recovered")

            metadata = decrypt_image_adaptive(
                encrypted_input_path=encrypted_path,
                output_image_path=str(output_path),
                metadata_path=metadata_path,
                passphrase=passphrase or None,
                recipient_private_key_pem=recipient_private_key_pem,
            )

            image_bytes = output_path.read_bytes()
            st.success("Decryption completed.")
            st.image(image_bytes, caption="Recovered image", use_container_width=True)

            st.download_button(
                "Download recovered image",
                data=image_bytes,
                file_name=output_path.name,
                mime="image/png",
            )

            with st.expander("Metadata used for decryption", expanded=False):
                st.json(metadata)
            if metadata.get("claims_boundary"):
                st.info(
                    "Claims boundary present in metadata. Keep publication claims tied to standard primitives."
                )

        except Exception as exc:  # noqa: BLE001
            st.error(f"Decryption failed: {exc}")

    if metadata_file is not None:
        try:
            preview = json.loads(metadata_file.getvalue().decode("utf-8"))
            st.subheader("Metadata preview")
            st.json(preview)
            security_context = preview.get("security_context", {})
            if security_context:
                st.caption("Security context from encryption run")
                st.json(security_context)
            key_exchange = preview.get("key_exchange", {})
            mode = str(key_exchange.get("mode", "passphrase_only"))
            st.caption(f"Expected key exchange mode: {mode}")
            if mode == "passphrase_only" and not passphrase:
                st.warning("Metadata expects passphrase_only mode. Provide passphrase before decrypting.")
            if mode in {"x25519_only", "hybrid_passphrase_x25519"} and recipient_private_key_pem is None:
                st.warning("Metadata expects X25519 private key for decryption.")
        except Exception:  # noqa: BLE001
            st.warning("Could not parse metadata JSON preview.")


if __name__ == "__main__":
    main()
