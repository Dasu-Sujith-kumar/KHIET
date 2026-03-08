# Testing, Entry Points, Commands, and Dataset Guide

## 1. Purpose

This document explains:

- how to start the project
- which files are the main entry points
- how to test the current implementation
- which commands to run
- what input images or datasets are needed

This guide is written for the current codebase as of 2026-03-08.

## 2. Environment Setup

Run all commands from the repository root:

```powershell
cd d:\Downloads\hybrid
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Current Python package requirements from `requirements.txt`:

- `numpy`
- `opencv-python`
- `cryptography`
- `onnxruntime`
- `streamlit`
- `Pillow`

## 3. Main Entry Points

### 3.1 CLI Entry Point

File:

- `main.py`

Purpose:

- encrypt an image
- decrypt an encrypted image

Check commands:

```powershell
python main.py --help
python main.py encrypt --help
python main.py decrypt --help
```

### 3.2 Evaluation Entry Point

File:

- `evaluate_pipeline.py`

Purpose:

- run ablation and security-engineering evaluation
- generate metrics JSON

Check command:

```powershell
python evaluate_pipeline.py --help
```

### 3.3 Key Management Entry Point

File:

- `key_manager.py`

Purpose:

- create base64 master keys
- create X25519 key pairs

Check command:

```powershell
python key_manager.py --help
python key_manager.py x25519 --help
```

### 3.4 Encryption UI Entry Point

File:

- `encrypt_app.py`

Purpose:

- Streamlit UI for interactive encryption

Start command:

```powershell
streamlit run encrypt_app.py
```

### 3.5 Decryption UI Entry Point

File:

- `decrypt_app.py`

Purpose:

- Streamlit UI for interactive decryption

Start command:

```powershell
streamlit run decrypt_app.py
```

## 4. Core Library-Level Entry Points

These are the main callable functions inside the project:

- `pipeline.encrypt.encrypt_array_adaptive`
- `pipeline.encrypt.encrypt_image_adaptive`
- `pipeline.decrypt.decrypt_array_adaptive`
- `pipeline.decrypt.decrypt_image_adaptive`
- `evaluate_pipeline.run`
- `key_manager.create_x25519_keypair`

These are useful if you want to integrate the project into another script later.

## 5. Minimum Input Needed to Run the Project

For the current codebase, the minimum dataset requirement is simple:

- at least one readable image file

Supported practical input formats:

- `.png`
- `.jpg`
- `.jpeg`
- `.bmp`
- `.webp`

For quick testing, the repository already contains a usable sample image:

- `artifacts\eval_smoke\input.png`

So for smoke testing, you do **not** need to download a dataset first.

## 6. Quick Start Commands

### 6.1 Passphrase-Only Encryption

```powershell
python main.py encrypt `
  --input artifacts\eval_smoke\input.png `
  --output artifacts\doc_smoke\out.enc `
  --metadata artifacts\doc_smoke\out.meta.json `
  --passphrase p@ss
```

### 6.2 Passphrase-Only Decryption

```powershell
python main.py decrypt `
  --input artifacts\doc_smoke\out.enc `
  --output artifacts\doc_smoke\out.dec.png `
  --metadata artifacts\doc_smoke\out.meta.json `
  --passphrase p@ss
```

### 6.3 Generate X25519 Keys

```powershell
python key_manager.py x25519 `
  --private artifacts\doc_smoke\priv.pem `
  --public artifacts\doc_smoke\pub.pem
```

### 6.4 X25519-Only Encryption

```powershell
python main.py encrypt `
  --input artifacts\eval_smoke\input.png `
  --output artifacts\doc_smoke\x25519.enc `
  --metadata artifacts\doc_smoke\x25519.meta.json `
  --recipient-public-key artifacts\doc_smoke\pub.pem
```

### 6.5 X25519-Only Decryption

```powershell
python main.py decrypt `
  --input artifacts\doc_smoke\x25519.enc `
  --output artifacts\doc_smoke\x25519.dec.png `
  --metadata artifacts\doc_smoke\x25519.meta.json `
  --recipient-private-key artifacts\doc_smoke\priv.pem
```

### 6.6 Hybrid Passphrase + X25519 Encryption

```powershell
python main.py encrypt `
  --input artifacts\eval_smoke\input.png `
  --output artifacts\doc_smoke\hybrid.enc `
  --metadata artifacts\doc_smoke\hybrid.meta.json `
  --passphrase p@ss `
  --recipient-public-key artifacts\doc_smoke\pub.pem
```

### 6.7 Hybrid Passphrase + X25519 Decryption

```powershell
python main.py decrypt `
  --input artifacts\doc_smoke\hybrid.enc `
  --output artifacts\doc_smoke\hybrid.dec.png `
  --metadata artifacts\doc_smoke\hybrid.meta.json `
  --passphrase p@ss `
  --recipient-private-key artifacts\doc_smoke\priv.pem
```

### 6.8 Evaluation / Ablation Run

```powershell
python evaluate_pipeline.py `
  artifacts\eval_smoke\input.png `
  --passphrase p@ss `
  --out-dir artifacts\doc_eval
```

Expected output file:

- `artifacts\doc_eval\evaluation_results.json`

## 7. What Was Verified in This Workspace

The following command paths were validated successfully in this repository:

- passphrase-only encrypt
- passphrase-only decrypt
- X25519 key generation
- X25519-only encrypt
- X25519-only decrypt
- hybrid encrypt
- hybrid decrypt
- evaluation runner

## 8. How to Test the Project Properly

There is currently **no dedicated `pytest` test suite** in the repository.

So the present testing approach is mainly:

- CLI smoke testing
- UI manual testing
- evaluation-runner validation
- negative-path security checks

### 8.1 Functional Smoke Tests

Run these first:

1. Encrypt and decrypt in `passphrase_only` mode.
2. Encrypt and decrypt in `x25519_only` mode.
3. Encrypt and decrypt in `hybrid_passphrase_x25519` mode.
4. Run `evaluate_pipeline.py`.

Success criteria:

- encryption writes `.enc` and `.meta.json`
- decryption writes a valid image
- decrypt command returns `"status": "ok"`
- evaluation writes `evaluation_results.json`

### 8.2 Manual UI Tests

Start:

```powershell
streamlit run encrypt_app.py
streamlit run decrypt_app.py
```

Manual checks:

- upload an image and encrypt it
- confirm metadata downloads correctly
- decrypt using the generated metadata and keys
- verify UI warnings change when key mode changes
- verify X25519 mode asks for PEM material

### 8.3 Negative and Security-Oriented Tests

These should also be performed:

#### Wrong Passphrase Test

- encrypt using one passphrase
- try to decrypt using a different passphrase
- expected result: decryption fails

#### Wrong Private Key Test

- encrypt in X25519 mode
- try to decrypt with the wrong private key
- expected result: decryption fails

#### Metadata Tampering Test

- edit a field in the metadata JSON manually
- expected result: metadata verification fails

#### Ciphertext Tampering Test

- modify one byte in the `.enc` file
- expected result: AES-GCM decryption fails

#### Output Integrity Test

- compare original image and decrypted image for a successful round trip
- expected result: reconstructed image matches the original

## 9. What the Evaluation Runner Measures

The evaluation runner currently produces:

- entropy
- adjacent correlation
- NPCR
- UACI
- key sensitivity
- PSNR
- MSE
- execution time
- peak memory
- bit-flip attack result
- noise attack result
- crop attack result
- ablation across:
  - `aes_only`
  - `static_chaos_aes`
  - `proposed_hardened`

Important note:

The attack checks currently test **tamper detection/failure behavior**, not graceful recovery. Under AES-GCM, decryption failure after tampering is expected.

## 10. Datasets Needed Right Now

For current development and basic testing:

- one image is enough

For better local testing:

- prepare 5 to 20 images with different characteristics

Recommended local categories:

- smooth low-detail images
- textured natural scenes
- portraits
- high-edge urban images
- dark and bright images

Suggested local folder structure:

```text
datasets/
  smoke/
    img01.png
    img02.png
    img03.png
  benchmark/
    natural/
    portrait/
    texture/
```

## 11. Datasets Recommended for Publication-Strength Evaluation

These are not bundled in the repository, but they are good categories to prepare if the project is being turned into a paper:

- a small natural-image benchmark such as Kodak-style image sets
- a mixed benchmark such as USC-SIPI style image groups
- an edge/diversity benchmark such as BSDS-style image sets
- a larger grayscale or steganalysis-style set such as BOSSBase-type data
- one domain-specific dataset if you want to make claims about medical, biometric, or surveillance scenarios

Important rule:

Only make domain-specific claims if you actually evaluate on domain-specific data.

## 12. What to Check in the Outputs

### 12.1 Encryption Outputs

You should see:

- ciphertext file such as `out.enc`
- metadata file such as `out.meta.json`

Check metadata for:

- `version`
- `profile`
- `threat_level`
- `key_exchange`
- `image_sha256_b64`
- `nonce_strategy`
- `metadata_hmac`

### 12.2 Decryption Outputs

You should see:

- recovered image file such as `out.dec.png`

Check:

- the image opens correctly
- the size matches the original image
- the content matches visually

### 12.3 Evaluation Outputs

You should see:

- `evaluation_results.json`

Check:

- metrics exist for all three variants
- timing and memory values are present
- ablation table is populated

## 13. Best Order for Testing

Use this order:

1. Install dependencies.
2. Run passphrase-only smoke test.
3. Generate X25519 keys.
4. Run X25519-only smoke test.
5. Run hybrid smoke test.
6. Run the evaluation harness.
7. Run negative-path tamper tests.
8. Run Streamlit UI tests.

## 14. Current Gaps in Testing

The project still needs:

- automated unit tests
- multi-image regression testing
- benchmark automation across folders
- statistical reporting across repeated runs
- baseline comparison automation against external methods

## 15. Short Honest Summary

The project is runnable now from CLI and Streamlit entry points.

The easiest way to test it is to use `artifacts\eval_smoke\input.png` and run the CLI commands in this document.

For publication work, one-image smoke testing is not enough. A real benchmark folder and repeated evaluation pipeline still need to be added.
