# Upgrades

## 2026-03 Adaptive Profile + UI Update

- Rebuilt core modules that were zeroed out in workspace
- Added adaptive profile feature across pipeline and UI
- Added authenticated metadata verification in decryption
- Added Streamlit UI flows for encryption/decryption with downloads
- Updated CLI entrypoint and evaluation utilities
- Updated dependency manifest

## 2026-03 Research-Hardening Update

- Added explicit domain-separated key roles (`K1` AES, `K2` nonce, `K3` chaos, `K4` metadata MAC)
- Added nonce derivation hardening via `HMAC-SHA256(K2, nonce_salt || context)`
- Added metadata fields for threat-model assumptions and claim boundaries
- Updated encryption/decryption UI to capture publication goal + adversary assumptions
- Updated architecture and roadmap markdowns for reviewer-resistant framing

## 2026-03 Strong Security-Engineering Update

- Added image-bound digest context into master derivation and chaos seed binding
- Added optional `passphrase_only`, `x25519_only`, `hybrid_passphrase_x25519` modes
- Added in-memory adaptive decryption API for benchmark/ablation workflows
- Replaced evaluation runner with full metrics + attack simulation + ablation table output
- Added metadata schema validation in `pipeline/metadata_io.py`
