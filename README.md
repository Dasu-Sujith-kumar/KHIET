# Hybrid Image Encryption (Security-Engineering Focus)

This project targets a reviewer-resistant security-engineering paper, not a new cipher proposal.

## Claim Boundary

This implementation does **not** claim:

- AES modification
- A new cryptographic primitive
- "Chaos stronger than AES"

It **does** claim:

- disciplined domain-separated key derivation
- image-bound seed/key context
- optional ephemeral X25519 forward-secrecy mode
- explicit threat-model mapping with reproducible evaluation

## Hardened Architecture

```
Input Image
  -> SHA-256(image || shape || dtype)
  -> (passphrase and/or ephemeral X25519 shared secret)
  -> HKDF-based master derivation
  -> Domain-separated keys: K_AES, K_Nonce, K_Chaos, K_Metadata
  -> Keyed chaos permutation (+ policy-driven Arnold map)
  -> AES-256-GCM payload encryption
  -> HMAC-authenticated metadata
```

## Key Roles

- `K1` (`aes_key`): AES-GCM payload confidentiality/integrity
- `K2` (`nonce_key`): nonce derivation
- `K3` (`chaos_key`): chaos seed derivation
- `K4` (`metadata_key`): metadata HMAC authentication

Nonce derivation:

- `nonce = HMAC-SHA256(K2, nonce_salt || deterministic_context)[:12]`

## Key Exchange Modes

- `passphrase_only`
- `x25519_only` (requires recipient public/private key pair)
- `hybrid_passphrase_x25519`

## Security Mapping

- Payload confidentiality/integrity -> AES-GCM assumptions
- Key exchange hardness (when enabled) -> X25519 assumptions
- KDF separation -> HKDF assumptions
- Metadata tamper detection -> HMAC-SHA256 assumptions

## Installation

```bash
pip install -r requirements.txt
```

## CLI Usage

Passphrase only:

```bash
python main.py encrypt --input sample.png --output out/sample.enc --metadata out/sample.meta.json --passphrase "p@ss"
python main.py decrypt --input out/sample.enc --output out/sample.dec.png --metadata out/sample.meta.json --passphrase "p@ss"
```

X25519 only:

```bash
python key_manager.py x25519 --private keys/recipient_private.pem --public keys/recipient_public.pem
python main.py encrypt --input sample.png --output out/sample.enc --metadata out/sample.meta.json --recipient-public-key keys/recipient_public.pem
python main.py decrypt --input out/sample.enc --output out/sample.dec.png --metadata out/sample.meta.json --recipient-private-key keys/recipient_private.pem
```

Hybrid mode:

```bash
python main.py encrypt --input sample.png --output out/sample.enc --metadata out/sample.meta.json --passphrase "p@ss" --recipient-public-key keys/recipient_public.pem
python main.py decrypt --input out/sample.enc --output out/sample.dec.png --metadata out/sample.meta.json --passphrase "p@ss" --recipient-private-key keys/recipient_private.pem
```

## UI

```bash
streamlit run encrypt_app.py
streamlit run decrypt_app.py
```

The UI now captures publication goal, adversary assumptions, strict-claims mode, and key-exchange mode.

## Evaluation / Ablation

Run:

```bash
python evaluate_pipeline.py sample.png --passphrase "p@ss" --out-dir artifacts/eval
```

Output includes:

- Entropy
- Correlation
- NPCR
- UACI
- Key sensitivity
- PSNR / MSE
- Execution time
- Peak memory
- Bit-flip / noise / cropping attack outcomes
- Ablation table for `aes_only`, `static_chaos_aes`, `proposed_hardened`

Optional (paper-style plots + deeper attack sweeps):

```bash
python evaluate_pipeline.py sample.png --passphrase "p@ss" --out-dir artifacts/eval --attack-suite high --report
```

This additionally writes:

- `artifacts/eval/report/report.html`
- multiple `.png` charts and `.csv` tables under `artifacts/eval/report/`

## Batch Encryption + Evaluation (100 images × 3 modes)

Create 3 folders (`passphrase_only`, `x25519_only`, `hybrid`) with `.enc` + `.meta.json` pairs and an aggregated report:

```bash
python batch_run.py datasets/smoke --out-dir artifacts/batch_run --count 100 --passphrase "p@ss" --report
```

Report:

- `artifacts/batch_run/evaluation/report/report.html`
