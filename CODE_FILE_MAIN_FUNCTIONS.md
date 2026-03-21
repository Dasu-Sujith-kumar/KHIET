# Code File Main Functions

This document explains what each Python file in this project mainly does.
It is a navigation guide, not a line-by-line code explanation.

## End-to-End Flow

The main runtime path is:

`main.py` or Streamlit app -> `pipeline/encrypt.py` / `pipeline/decrypt.py` -> `adaptive/*` + `chaso/*` + `crypto/*` + `pipeline/metadata_io.py`

The evaluation path is:

`evaluate_pipeline.py` -> `evaluation/*` + pipeline helpers

## Top-Level Scripts

| File | Main responsibility | Main functions/classes |
| --- | --- | --- |
| `main.py` | Command-line entrypoint for encryption and decryption. Parses CLI arguments, builds security-context metadata, and calls the adaptive pipeline. | `_build_parser()`, `main()` |
| `encrypt_app.py` | Streamlit UI for encrypting images. Handles uploads, passphrase/X25519 options, artifact naming, and result download. | `_save_uploaded_image()`, `_artifact_paths()`, `_resolve_pem_input()`, `_render_encrypt_result()`, `main()` |
| `decrypt_app.py` | Streamlit UI for decrypting encrypted files using metadata. Detects required key mode from metadata and renders recovered images. | `_write_temp()`, `_output_image_path()`, `_resolve_pem_input()`, `_parse_metadata_preview()`, `_expected_key_exchange_mode()`, `_render_decrypt_result()`, `main()` |
| `evaluate_pipeline.py` | Evaluation and ablation runner. Compares `aes_only`, `static_chaos_aes`, and `proposed_hardened`, then writes a JSON report with metrics, timing, memory, and attack outcomes. | `_variant_aes_only()`, `_variant_static_chaos_aes()`, `_variant_proposed_hardened()`, `_build_metrics_block()`, `run()`, `main()` |
| `batch_run.py` | Batch runner that encrypts N images in 3 key-exchange modes (passphrase/X25519/hybrid), then evaluates attacks/metrics across all pairs and generates an aggregated report. | `run()`, `main()` |
| `key_manager.py` | Utility script for generating random symmetric master keys and X25519 key pairs. | `write_key_file()`, `read_key_file()`, `create_master_key_file()`, `create_x25519_keypair()`, `main()` |
| `graph.py` | Standalone plotting script for visualizing model-style charts and benchmark graphs. It is presentation/demo code, not part of the encryption pipeline. | `clean_plot()` |

## Adaptive Package

| File | Main responsibility | Main functions/classes |
| --- | --- | --- |
| `adaptive/classifier.py` | Heuristic image sensitivity classifier. Scores an image using grayscale entropy, edge density, and variance, then labels it as `low`, `medium`, or `high`. | `ClassificationResult`, `SensitivityClassifier.classify()`, `_entropy_u8()`, `_to_gray()`, `_edge_density()` |
| `adaptive/policy.py` | Maps classifier output and threat level to a runtime security profile (`lite`, `standard`, `max`). | `SecurityProfile`, `select_security_profile()` |
| `adaptive/__init__.py` | Package export file. Re-exports the classifier and policy API for easier imports elsewhere. | `ClassificationResult`, `SensitivityClassifier`, `SecurityProfile`, `select_security_profile` |

## Chaos / Transform Package

| File | Main responsibility | Main functions/classes |
| --- | --- | --- |
| `chaso/arnold_map.py` | Implements the reversible Arnold cat map for square images. Used as an optional scrambling stage before AES encryption. | `arnold_map()`, `inverse_arnold_map()`, `_validate_square_image()` |
| `chaso/keyed_permutation.py` | Implements deterministic keyed permutation rounds over flattened image data. Also derives the integer chaos seed from key material. | `derive_chaos_seed()`, `adaptive_permute()`, `inverse_adaptive_permute()`, `_round_seed()` |
| `chaso/__init__.py` | Package export file for transform helpers. | `arnold_map`, `inverse_arnold_map`, `adaptive_permute`, `inverse_adaptive_permute`, `derive_chaos_seed` |

## Cryptography Package

| File | Main responsibility | Main functions/classes |
| --- | --- | --- |
| `crypto/aes_gcm.py` | AES-GCM encryption/decryption helpers plus deterministic nonce derivation from a dedicated nonce key and nonce salt. | `derive_gcm_nonce()`, `encrypt_aes()`, `decrypt_aes()` |
| `crypto/key_schedule.py` | Key derivation core. Builds the master key from passphrase and/or shared secret plus image digest, then expands it into domain-separated subkeys for AES, nonce, chaos, and metadata MAC. | `DerivedKeys`, `generate_master_key()`, `generate_kdf_salt()`, `master_key_from_passphrase()`, `derive_master_key_material()`, `derive_subkeys()` |
| `crypto/metadata_auth.py` | Canonicalizes metadata JSON and authenticates it with HMAC-SHA256. | `sign_metadata()`, `verify_metadata()`, `_canonical_metadata_bytes()` |
| `crypto/ecc_keywrap.py` | X25519-based helper for optional public-key support. Generates X25519 keys and wraps or unwraps a symmetric key using an ephemeral shared secret and AES-GCM. | `generate_keys()`, `wrap_key()`, `unwrap_key()`, `_derive_wrap_key()` |
| `crypto/__init__.py` | Package export file for crypto helpers. | Re-exports AES, KDF, and X25519 helper functions |

## Pipeline Package

| File | Main responsibility | Main functions/classes |
| --- | --- | --- |
| `pipeline/adaptive_common.py` | Shared pipeline utilities: base64 conversion, image load/save, square padding, unpadding, and image digest generation. | `b64_encode_bytes()`, `b64_decode_bytes()`, `load_image()`, `save_image()`, `pad_to_square()`, `unpad_from_square()`, `image_sha256_digest()` |
| `pipeline/encrypt.py` | Core adaptive encryption pipeline. Selects the profile, derives keys, applies Arnold map and keyed permutation, encrypts with AES-GCM, then builds and signs metadata. | `encrypt_array_adaptive()`, `encrypt_image_adaptive()`, `encrypt_image()`, `_derive_shared_secret()`, `_build_metadata()`, `_nonce_context()`, `_aad()` |
| `pipeline/decrypt.py` | Core adaptive decryption pipeline. Re-derives keys from metadata and credentials, verifies metadata HMAC, decrypts AES-GCM payload, reverses permutation/Arnold map, and restores the image. | `decrypt_array_adaptive()`, `decrypt_image_adaptive()`, `decrypt_image()`, `_shared_secret_from_metadata()`, `_verify_metadata()`, `_nonce_context()`, `_aad()` |
| `pipeline/metadata_io.py` | Reads, validates, and writes metadata JSON files used by the pipeline. | `validate_metadata()`, `write_metadata()`, `read_metadata()` |
| `pipeline/__init__.py` | Package export file for the encrypt/decrypt pipeline entrypoints. | `encrypt_array_adaptive`, `encrypt_image`, `encrypt_image_adaptive`, `decrypt_array_adaptive`, `decrypt_image`, `decrypt_image_adaptive` |

## Evaluation Package

| File | Main responsibility | Main functions/classes |
| --- | --- | --- |
| `evaluation/metrics.py` | Implements the quantitative metrics used in the project: entropy, NPCR, UACI, PSNR, MSE, adjacent correlation, and key sensitivity. | `shannon_entropy()`, `npcr()`, `uaci()`, `psnr()`, `mse()`, `adjacent_correlation()`, `key_sensitivity()` |
| `evaluation/attacks.py` | Provides simple perturbation helpers used during robustness checks, such as random bit-flip, Gaussian byte noise, and center crop. | `flip_random_bit()`, `add_gaussian_noise_to_bytes()`, `crop_image_center()` |
| `evaluation/reporting.py` | Generates paper-style plots + an HTML report from `evaluation_results.json` (and is called by `evaluate_pipeline.py --report`). | `write_evaluation_report()`, `main()` |
| `evaluation/__init__.py` | Package export file for evaluation metrics and attack helpers. | Re-exports functions from `metrics.py` and `attacks.py` |

## Which Files Matter Most First

If someone is new to the project, read these first:

1. `main.py`
2. `pipeline/encrypt.py`
3. `pipeline/decrypt.py`
4. `adaptive/classifier.py`
5. `adaptive/policy.py`
6. `crypto/key_schedule.py`
7. `crypto/aes_gcm.py`
8. `pipeline/metadata_io.py`
9. `evaluate_pipeline.py`

That order gives the clearest picture of how the project works from input image to encrypted output and back.
