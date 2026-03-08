"""Streamlit UI for adaptive image decryption."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from pipeline.decrypt import decrypt_image_adaptive

DECRYPT_RESULT_KEY = "decrypt_result"


def _write_temp(uploaded_file: Any, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as fh:
        fh.write(uploaded_file.getbuffer())
        return fh.name


def _output_image_path(stem: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{stem}_{ts}.decrypted.png"


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


def _parse_metadata_preview(metadata_file: Any | None) -> dict[str, Any] | None:
    if metadata_file is None:
        return None

    try:
        return json.loads(metadata_file.getvalue().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _expected_key_exchange_mode(metadata_preview: dict[str, Any] | None) -> str | None:
    if metadata_preview is None:
        return None
    key_exchange = metadata_preview.get("key_exchange", {})
    return str(key_exchange.get("mode", "passphrase_only"))


def _render_decrypt_result(result: dict[str, Any]) -> None:
    output_path = Path(result["output_path"])
    if not output_path.is_file():
        st.session_state.pop(DECRYPT_RESULT_KEY, None)
        st.warning("Latest decrypted artifact was removed. Decrypt again to regenerate the download.")
        return

    image_bytes = output_path.read_bytes()
    metadata = result["metadata"]

    st.subheader("Latest decryption result")
    if result.get("source_name"):
        st.caption(f"Encrypted input: {result['source_name']}")

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
        st.info("Claims boundary present in metadata. Keep publication claims tied to standard primitives.")


def main() -> None:
    st.set_page_config(page_title="Hybrid Decrypt", layout="wide")
    st.title("Adaptive Hybrid Decryption")
    st.caption("Upload encrypted bytes + metadata JSON from the encryption app.")

    encrypted_file = st.file_uploader("Encrypted file (.enc/.bin)", type=["enc", "bin", "dat"])
    metadata_file = st.file_uploader("Metadata JSON", type=["json"])
    metadata_preview = _parse_metadata_preview(metadata_file)
    expected_mode = _expected_key_exchange_mode(metadata_preview)

    passphrase = ""
    if expected_mode in {None, "passphrase_only", "hybrid_passphrase_x25519"}:
        passphrase = st.text_input("Passphrase", type="password")

    recipient_private_key_pem_text = ""
    recipient_private_key_pem_file = None
    if expected_mode in {None, "x25519_only", "hybrid_passphrase_x25519"}:
        recipient_private_key_pem_text = st.text_area(
            "Recipient X25519 private key PEM",
            help="Paste PEM text or enter a local .pem path. Required when metadata uses X25519.",
            height=140,
        )
        recipient_private_key_pem_file = st.file_uploader(
            "Or upload recipient private key (.pem)",
            type=["pem"],
            accept_multiple_files=False,
        )

    if metadata_file is None:
        st.info("Upload metadata JSON first to show only the decryption inputs required for that file.")

    recipient_private_key_pem = _resolve_pem_input(
        recipient_private_key_pem_text,
        recipient_private_key_pem_file,
    )
    if expected_mode == "passphrase_only":
        ready = encrypted_file is not None and metadata_file is not None and bool(passphrase)
    elif expected_mode == "x25519_only":
        ready = encrypted_file is not None and metadata_file is not None and recipient_private_key_pem is not None
    elif expected_mode == "hybrid_passphrase_x25519":
        ready = (
            encrypted_file is not None
            and metadata_file is not None
            and bool(passphrase)
            and recipient_private_key_pem is not None
        )
    else:
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
            st.session_state[DECRYPT_RESULT_KEY] = {
                "output_path": str(output_path),
                "metadata": metadata,
                "source_name": encrypted_file.name,
            }

        except Exception as exc:  # noqa: BLE001
            st.session_state.pop(DECRYPT_RESULT_KEY, None)
            st.error(f"Decryption failed: {exc}")

    result = st.session_state.get(DECRYPT_RESULT_KEY)
    if result is not None:
        _render_decrypt_result(result)

    if metadata_file is not None:
        if metadata_preview is not None:
            preview = metadata_preview
            st.subheader("Metadata preview")
            st.json(preview)
            security_context = preview.get("security_context", {})
            if security_context:
                st.caption("Security context from encryption run")
                st.json(security_context)
            st.caption(f"Expected key exchange mode: {expected_mode}")
            if expected_mode == "passphrase_only" and not passphrase:
                st.warning("Metadata expects passphrase_only mode. Provide passphrase before decrypting.")
            if expected_mode in {"x25519_only", "hybrid_passphrase_x25519"} and recipient_private_key_pem is None:
                st.warning("Metadata expects X25519 private key for decryption.")
            if expected_mode == "hybrid_passphrase_x25519" and not passphrase:
                st.warning("Metadata expects both passphrase and X25519 private key for decryption.")
        else:
            st.warning("Could not parse metadata JSON preview.")


if __name__ == "__main__":
    main()
