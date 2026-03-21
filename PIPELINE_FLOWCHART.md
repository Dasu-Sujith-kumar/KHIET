# Pipeline Flowcharts (Encryption, Decryption, Batch Evaluation)

This file provides **report-friendly** flowcharts for the current hybrid image-encryption project.

## 1) Encryption Pipeline

```mermaid
flowchart TD
  A[Input Image] --> B[Load as uint8 BGR]
  B --> C[Sensitivity Classifier<br/>(entropy, edge density, variance)]
  C --> D[Select Security Profile<br/>(lite / standard / max)]
  B --> E[Image SHA-256 digest<br/>(image || shape || dtype)]

  P[Passphrase (optional)] --> K
  X[Recipient Public Key (optional)] --> X1[X25519 ECDH<br/>ephemeral shared secret]
  X1 --> K
  E --> K[Derive Master Key Material<br/>PBKDF2 + HKDF (image-bound)]
  K --> S[Derive Subkeys (HKDF domain-separated)<br/>K1 AES | K2 nonce | K3 chaos | K4 metadata HMAC]

  D --> T[Transform Stage]
  S --> T
  T --> T1[Optional pad-to-square]
  T1 --> T2[Optional Arnold map iterations]
  T2 --> T3[Keyed permutation rounds<br/>(seed from K3)]

  S --> N[Nonce derivation<br/>HMAC-SHA256(K2, nonce_salt || context)[:12]]
  T3 --> G[AES-256-GCM Encrypt (K1, nonce, AAD)]
  N --> G

  C --> M[Metadata assembly<br/>(classification + profile + salts + nonce context + key mode)]
  D --> M
  S --> H[Metadata HMAC (K4)]
  M --> H

  G --> OUT1[Ciphertext .enc]
  H --> OUT2[Metadata .meta.json]
```

## 2) Decryption Pipeline

```mermaid
flowchart TD
  IN1[Ciphertext .enc] --> A
  IN2[Metadata .meta.json] --> A[Read + validate metadata]

  A --> X{X25519 mode?}
  X -- yes --> X1[Use recipient private key<br/>to derive shared secret]
  X -- no --> K
  P[Passphrase (optional)] --> K
  X1 --> K[Re-derive master key (image-bound)]
  K --> S[Re-derive subkeys K1..K4]

  S --> V[Verify metadata HMAC (K4)]
  V --> N[Derive nonce from K2 + nonce_salt + context]
  N --> G[AES-256-GCM Decrypt (K1)]
  G --> T3[Inverse keyed permutation]
  T3 --> T2[Inverse Arnold map (if used)]
  T2 --> T1[Unpad from square (if used)]
  T1 --> OUT[Recovered image]
```

## 3) Batch Run (100 images × 3 modes)

`batch_run.py` runs the same encryption pipeline in three key modes and then evaluates every output:

```mermaid
flowchart TD
  D[Input image folder] --> L[List images]
  L --> S[Select N images]

  S --> K[Create or load X25519 keypair<br/>(reused for x25519_only + hybrid)]

  S --> E1[Encrypt passphrase_only]
  K --> E2[Encrypt x25519_only]
  S --> E2
  K --> E3[Encrypt hybrid]
  S --> E3

  E1 --> O1[passphrase_only/*.enc + *.meta.json]
  E2 --> O2[x25519_only/*.enc + *.meta.json]
  E3 --> O3[hybrid/*.enc + *.meta.json]

  O1 --> EV[Evaluate all pairs]
  O2 --> EV
  O3 --> EV

  EV --> R1[batch_results.csv / batch_results.json]
  EV --> R2[Aggregated HTML report + charts]
```

## Notes (what the attack graphs mean)

- Many simulated attacks intentionally produce **decryption failure** under AES-GCM (this is expected).
- So the most meaningful visualization is often **detection rate** (i.e., `1 - decrypt_success_rate`).

