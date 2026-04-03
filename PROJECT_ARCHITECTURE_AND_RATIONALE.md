# Project Architecture, Pipeline, Definitions, Weaknesses, and Publication Rationale

## 1. Executive Summary

This project is a **security-engineering image protection framework**. It combines:

- adaptive profile selection
- image-bound key derivation
- keyed permutation and optional Arnold transform
- AES-256-GCM payload encryption
- HMAC-authenticated metadata
- optional X25519-based key exchange

The key point is this:

**The project should not be positioned as a brand-new cipher.**

It is better positioned as a **hardened hybrid framework** that fixes common design mistakes seen in many chaos-based image-encryption systems, while staying grounded in standard cryptographic primitives.

That makes it:

- strong as a final-year project
- defendable in a viva
- useful as a security-engineering prototype
- potentially publishable if framed correctly

It does **not** automatically become a strong journal paper just because it uses chaos, AES, ECC, and an adaptive classifier.

## 2. What This Project Does

At a high level, the system takes an image and:

1. Estimates image sensitivity.
2. Chooses an encryption profile.
3. Derives keys from the image digest and user credentials.
4. Applies reversible image scrambling.
5. Encrypts the transformed image with AES-GCM.
6. Stores authenticated metadata needed for safe decryption.

The result is a framework that aims to improve:

- key separation
- seed unpredictability
- metadata integrity
- traceability of security assumptions
- reproducible evaluation

## 3. Architecture Overview

```text
Input Image
  -> Sensitivity Classifier
  -> Security Profile Selection
  -> Image SHA-256 Digest
  -> Passphrase and/or X25519 Shared Secret
  -> HKDF-Based Master Key Derivation
  -> Domain-Separated Subkeys: K1, K2, K3, K4
  -> Optional Arnold Map
  -> Keyed Permutation
  -> AES-256-GCM Encryption
  -> Metadata Assembly
  -> Metadata HMAC Authentication
  -> Encrypted Payload + Metadata JSON
```

## 4. Main Components

### 4.1 Adaptive Layer

The adaptive layer decides how strong the transform stage should be.

- File: `adaptive/classifier.py`
- File: `adaptive/policy.py`

Current behavior:

- The classifier is now **ML-first**.
- It tries to load a finetuned Random Forest model and falls back to the earlier heuristic if the model is unavailable.
- The current model predicts image classes such as:
  - `faces`
  - `forms`
  - `land-scapes and others`
  - `manga`
  - `medical`
- Those classes are then mapped into sensitivity labels:
  - `low`
  - `medium`
  - `high`
- The learned feature set is still lightweight:
  - grayscale entropy
  - edge density
  - normalized variance
  - intensity statistics
  - small resized grayscale pixel features

That label is then combined with a user-selected threat level:

- `speed`
- `balanced`
- `hardened`

And mapped to one of three profiles:

- `lite`
- `standard`
- `max`

### 4.2 Cryptographic Core

The cryptographic core is the strongest part of the system because it relies on standard primitives.

- File: `crypto/key_schedule.py`
- File: `crypto/aes_gcm.py`
- File: `crypto/metadata_auth.py`

It uses:

- PBKDF2-HMAC-SHA256 for passphrase hardening
- HKDF-SHA256 for master-key expansion and domain separation
- AES-256-GCM for payload confidentiality and integrity
- HMAC-SHA256 for metadata authentication

### 4.3 Optional Public-Key Layer

- File: `crypto/ecc_keywrap.py`
- File: `pipeline/encrypt.py`
- File: `pipeline/decrypt.py`

The current pipeline supports:

- `passphrase_only`
- `x25519_only`
- `hybrid_passphrase_x25519`

This allows the framework to support a forward-secrecy-capable mode when X25519 is used.

### 4.4 Transform Layer

- File: `chaso/keyed_permutation.py`
- File: `chaso/arnold_map.py`

This layer performs reversible scrambling before AES-GCM encryption:

- keyed permutation using a seed derived from `K3`
- optional Arnold cat map for square working images

This is mainly a preprocessing and diffusion layer, not the primary source of confidentiality.

### 4.5 Metadata Layer

- File: `pipeline/metadata_io.py`
- File: `crypto/metadata_auth.py`

Metadata stores:

- version
- selected profile
- threat level
- salts
- nonce data
- image digest
- shape and dtype
- chaos seed
- key-exchange mode
- claims boundary
- security context

That metadata is authenticated with HMAC to detect tampering.

### 4.6 Evaluation Layer

- File: `evaluate_pipeline.py`
- File: `evaluation/metrics.py`
- File: `evaluation/attacks.py`

The project already evaluates:

- entropy
- adjacent correlation
- NPCR
- UACI
- key sensitivity
- PSNR
- MSE
- execution time
- peak memory
- bit-flip attack behavior
- noise attack behavior
- crop attack behavior
- ablation across three variants

## 5. End-to-End Pipeline

## 5.1 Encryption Pipeline

1. Load the image.
2. Compute image sensitivity metrics.
3. Select a security profile.
4. Compute `SHA-256(image || shape || dtype)`.
5. Combine:
   - passphrase-derived material and/or
   - X25519 shared secret and
   - image digest and
   - random salt
6. Derive a master key.
7. Expand the master key into four subkeys:
   - `K1`: AES key
   - `K2`: nonce key
   - `K3`: chaos key
   - `K4`: metadata HMAC key
8. If required by the profile, pad the image to a square.
9. If required by the profile, apply Arnold map iterations.
10. Derive a keyed chaos seed from `K3`.
11. Apply keyed permutation rounds.
12. Build AEAD associated data from version, profile, and threat level.
13. Derive the AES-GCM nonce using `K2`, a nonce salt, and deterministic context.
14. Encrypt the transformed bytes using AES-256-GCM.
15. Build metadata.
16. Authenticate metadata with HMAC-SHA256.
17. Save ciphertext and metadata.

## 5.2 Decryption Pipeline

1. Read ciphertext and metadata.
2. Reconstruct the shared secret if X25519 mode was used.
3. Re-derive the master key from the same inputs.
4. Re-derive the four domain-separated keys.
5. Verify metadata HMAC.
6. Recompute the nonce if nonce-salt mode is present.
7. Decrypt the ciphertext using AES-GCM.
8. Rebuild the permuted array.
9. Reverse the keyed permutation.
10. Reverse the Arnold transform if it was used.
11. Remove square padding if applied.
12. Restore the final image.

## 6. Definitions

### 6.1 Adaptive Encryption

Adaptive encryption means the system changes internal settings based on the input image and the selected threat posture instead of always using one fixed transform strength.

### 6.2 Image-Bound Key Derivation

Image-bound key derivation means the derived key material depends not only on the user credential, but also on the hash of the image content and image structure. This reduces blind reuse of the same effective key context across different images.

### 6.3 Domain Separation

Domain separation means different security functions use different keys, even when those keys come from one master secret.

In this project:

- `K1` protects payload encryption
- `K2` derives the AES-GCM nonce
- `K3` drives the permutation seed
- `K4` authenticates metadata

### 6.4 AES-GCM

AES-GCM is an authenticated encryption mode. It provides:

- confidentiality
- integrity
- authentication of the encrypted payload

If ciphertext or associated data is modified, decryption should fail.

### 6.5 X25519

X25519 is an elliptic-curve Diffie-Hellman key exchange mechanism. In this project it is used to derive a shared secret between the sender and recipient.

### 6.6 Arnold Map

The Arnold map is a reversible pixel-position scrambling transform typically used in image encryption literature. By itself it is not sufficient as a modern cryptographic primitive.

### 6.7 NPCR and UACI

These are common image-encryption diffusion metrics:

- NPCR measures how many pixel values change after a small change in input
- UACI measures the average intensity difference caused by that input change

### 6.8 Key Sensitivity

Key sensitivity measures how much ciphertext changes when the encryption key or passphrase changes slightly.

## 7. Why a Simple Chaos + AES + ECC + Classifier Design Is Not Automatically Novel

This is the honest part.

Many papers already combine:

- chaos
- AES
- ECC or DH-style key exchange
- some adaptive or intelligent control

So the raw combination is usually **not enough** for a strong paper.

Main reasons:

### 7.1 Combination Alone Is Common

Chaos + AES + ECC has been published many times. Reviewers will ask what is actually new.

### 7.2 Classifier Alone Does Not Guarantee Security Gain

If the adaptive layer only says "high sensitivity gets stronger scrambling", reviewers will ask:

- Does that improve confidentiality measurably?
- Does it reduce attack success?
- Does it improve efficiency in a meaningful way?

Without evidence, it looks like an engineering convenience, not a research contribution.

### 7.3 Chaos Layer Is Often Oversold in Literature

A common mistake is to imply that chaos is cryptographically stronger than standard encryption. That is not a safe claim. In a rigorous paper, AES-GCM is the real confidentiality and integrity anchor.

### 7.4 Statistical Metrics Alone Do Not Prove Security

Good entropy, NPCR, and UACI are useful, but they do not replace:

- formal threat analysis
- reduction-style reasoning
- attack modeling
- comparison against serious baselines

## 8. Common Weaknesses in Typical Hybrid Image-Encryption Papers

Below are the weaknesses often seen in chaos-based hybrid systems.

### 8.1 Key Reuse Across Multiple Roles

Weakness:

Many designs use one password or one raw secret directly for:

- AES key
- chaos seed
- nonce
- metadata integrity

Why this is bad:

- poor separation of failure domains
- easier cross-layer misuse
- weaker security reasoning

### 8.2 Reused or Predictable Chaos Seeds

Weakness:

Some systems use static seeds or seeds weakly derived from the password.

Why this is bad:

- repeated permutation patterns
- lower unpredictability
- weaker defense under repeated use

### 8.3 Weak Nonce Handling

Weakness:

Some systems generate nonces carelessly or bind them to the wrong context.

Why this is bad:

- AEAD misuse risk
- broken integrity/confidentiality guarantees if nonce discipline fails

### 8.4 Unauthenticated Metadata

Weakness:

Many projects save parameters in plain JSON without authentication.

Why this is bad:

- attacker can tamper with profile, seed, shape, or mode
- decryption can fail unpredictably
- research claims become harder to trust

### 8.5 No Clear Threat Model

Weakness:

A lot of papers report metrics but never state what attacker is being considered.

Why this is bad:

- claims become vague
- results are hard to interpret
- reviewers can reject the paper as incomplete

### 8.6 Overclaiming Novelty

Weakness:

Some papers describe a rearrangement of known blocks as a new secure encryption algorithm.

Why this is bad:

- reviewers push back
- claims are easy to challenge
- publication positioning becomes weak

### 8.7 Weak Reproducibility

Weakness:

Papers often do not provide clean ablations, fixed settings, attack scripts, or benchmark harnesses.

Why this is bad:

- difficult to reproduce
- difficult to compare fairly
- weakens publication quality

## 9. What This Project Has Already Done to Solve Those Weaknesses

This is where the project is stronger than many basic hybrid implementations.

### 9.1 Solved: Key Reuse Across Roles

Implemented solution:

- domain-separated key derivation through HKDF
- separate keys for AES, nonce derivation, chaos seed derivation, and metadata HMAC

Why this matters:

- cleaner security boundaries
- easier reasoning
- stronger engineering discipline

### 9.2 Solved: Static or Weak Seed Derivation

Implemented solution:

- chaos seed is derived from `K3`
- derivation includes image digest and salt

Why this matters:

- avoids naive static seed reuse
- ties transform behavior to both credential material and image context

### 9.3 Solved: Weak Nonce Strategy

Implemented solution:

- nonce is derived using a dedicated nonce key `K2`
- nonce derivation includes nonce salt and deterministic context

Why this matters:

- improves nonce discipline
- avoids reusing the AES key directly for nonce construction

### 9.4 Solved: Metadata Tampering Risk

Implemented solution:

- metadata is authenticated using HMAC-SHA256 with `K4`

Why this matters:

- detects tampering
- binds decryption parameters to authenticated state

### 9.5 Solved: Missing Claims Boundary

Implemented solution:

- metadata explicitly records that the system does not claim to modify AES or introduce a new primitive
- security claims are mapped to standard assumptions

Why this matters:

- more honest research positioning
- lower reviewer resistance

### 9.6 Solved: Missing Threat-Model Context

Implemented solution:

- security context stores publication goal and adversary assumptions
- threat-model fields are embedded in metadata

Why this matters:

- improves explainability
- helps connect experiments to explicit attacker models

### 9.7 Solved: Missing Evaluation and Ablation

Implemented solution:

- an evaluation runner already compares:
  - `aes_only`
  - `static_chaos_aes`
  - `proposed_hardened`
- attack simulations and timing/memory data are included

Why this matters:

- the project can support a real ablation section
- this is much stronger than a one-shot demo

## 10. Current Weaknesses That Still Remain

This section is important if the goal is a real publication.

### 10.1 The Adaptive Layer Is Learned, but Still Lightweight

Current reality:

- the current pipeline now includes a trained Random Forest adaptive classifier
- it is dataset-backed, but still based on lightweight grayscale statistics and downsampled pixel features
- it is not a semantic vision model such as MobileNet, ArcFace, or a privacy-aware document/face/OCR stack

Why this matters:

- the project can now defensibly claim a lightweight learned adaptive layer
- but reviewers may still ask whether the labels, features, and evaluation design are strong enough for bigger AI claims
- the remaining weakness is no longer "there is no learned model"; it is "the learned model is still relatively simple and needs stronger benchmarking"

### 10.2 No Formal Security Proof

Current reality:

- the project maps claims to standard primitives
- but it does not yet provide a formal security-game proof or reduction-style appendix

Why this matters:

- strong journals want tighter reasoning

### 10.3 Limited Benchmark Breadth

Current reality:

- the repository includes a smoke-style evaluation harness
- it does not yet provide a large multi-image benchmark with confidence intervals

Why this matters:

- single-image or few-image results are not enough for strong publication

### 10.4 Limited External Baseline Comparison

Current reality:

- ablation exists inside the project
- direct comparison against many recent published methods is not yet automated

Why this matters:

- publication quality depends heavily on comparative evidence

### 10.5 Chaos Layer Still Needs Careful Positioning

Current reality:

- the transform layer is useful as diffusion/scrambling
- it should not be presented as the main confidentiality mechanism

Why this matters:

- overclaiming here would weaken the paper

### 10.6 Robustness and Tamper Recovery Are Not the Goal

Current evaluation behavior:

- bit-flip, noise, and crop attacks cause decryption failure

This is not necessarily a bug.

Why:

- AES-GCM is designed to detect tampering, not recover gracefully from modified ciphertext

But publication risk:

- if the paper confuses integrity failure with robustness weakness, the presentation becomes unclear

## 11. How the Project Works in Plain Language

If someone asks, "What does this project actually do?", the simplest answer is:

It protects an image by first deciding how much scrambling is needed, then derives multiple safe-use keys from the image and credentials, then scrambles the image in a reversible way, encrypts it with AES-GCM, and saves only authenticated metadata required to reverse the process securely.

In other words:

- the adaptive layer decides the strength profile
- the transform layer rearranges the image
- AES-GCM does the real secure encryption
- HMAC protects the metadata
- X25519 optionally adds public-key-based key agreement

## 12. Usefulness of the Project

Yes, the project is useful.

Not because it invents a new cipher, but because it demonstrates a much better way to build and evaluate a hybrid image-encryption system.

Practical usefulness:

- educational value for security-engineering design
- a defendable final-year implementation
- a testbed for ablation and attack evaluation
- a base for publication-oriented refinement
- a better alternative to many weak chaos-only demos

Research usefulness:

- shows how to anchor claims to standard cryptography
- shows how to separate keys by role
- shows how to authenticate metadata properly
- shows how to evaluate a hybrid system more honestly

## 13. What Makes It Publishable, and What Does Not

### 13.1 What It Is Strong Enough For Right Now

In its current form, it is strong for:

- project report
- final-year defense
- demo paper
- poster
- low-tier or practice-oriented conference submission

### 13.2 What It Is Not Yet Strong Enough For

In its current form, it is not automatically strong enough for:

- a serious cryptography paper
- a high-impact security journal
- a top-quality methods paper claiming major algorithmic novelty

### 13.3 Best Publication Positioning

The best way to present it is something like:

**"A Security-Engineered Adaptive Hybrid Image Protection Framework with Domain-Separated Key Derivation, Authenticated Metadata, and Reproducible Evaluation."**

That is much stronger than claiming:

**"A Novel Chaos-AES-ECC Encryption Algorithm."**

## 14. What Should Be Improved to Make It a Stronger Publication

These are the highest-value next steps.

### 14.1 Add Strong External Comparisons

Add comparisons against 5 to 10 recent papers and report:

- entropy
- correlation
- NPCR
- UACI
- runtime
- memory
- key sensitivity
- attack behavior

This is one of the most important gaps.

### 14.2 Build a Real Benchmark Harness

Use:

- multiple datasets
- multiple image sizes
- multiple content categories
- repeated runs
- mean and standard deviation
- confidence intervals

This will make the evaluation more credible.

### 14.3 Upgrade the Adaptive Layer

The first upgrade is already done: the current pipeline now uses a trained lightweight Random Forest model with heuristic fallback.

If you want to make the adaptive contribution stronger from here, extend the current ML layer with:

- dataset-backed labeling
- ablation comparing heuristic vs learned policy
- confidence-aware fallback behavior
- stronger semantic/privacy features such as OCR, document cues, or face-aware signals

Without this next step, the "AI" angle is better than before, but it is still a lightweight adaptive-policy contribution rather than a strong computer-vision contribution.

### 14.4 Add Formal Security Analysis

At minimum, write a careful appendix that explains:

- what confidentiality relies on
- what integrity relies on
- what metadata authentication relies on
- what forward secrecy relies on
- what the chaos layer does and does not guarantee

This alone can significantly improve paper quality.

### 14.5 Strengthen Reproducibility

Add:

- dataset manifest
- fixed experiment config files
- environment lock file
- scriptable table generation
- seed control for evaluation

Reviewers value this.

### 14.6 Add Real Comparative Narrative

Do not only report numbers. Explain:

- why some results improve
- where the cost comes from
- when adaptive mode is worth using
- when AES-only is already sufficient

That makes the work sound more mature and honest.

### 14.7 Consider Reframing the Paper

The strongest paper angle may be one of these:

1. security-engineering hardening of hybrid image encryption
2. evaluation and practical enhancement of chaos-crypto hybrids
3. adaptive policy-driven image protection with authenticated metadata and reproducibility

This is a better fit than claiming a radically new encryption primitive.

## 15. Final Honest Assessment

This project is:

- technically solid
- well structured
- much better engineered than a basic chaos-encryption demo
- honest in its claim boundary
- useful for teaching, evaluation, and extension

It is **not yet groundbreaking**, but it is a very good base.

The strongest improvement already implemented is not "more chaos".

It is:

- disciplined key derivation
- authenticated metadata
- image-bound context
- optional X25519 mode
- explicit threat modeling
- reproducible ablation support

That is the right direction.

## 16. Recommended One-Line Positioning for Your Report or Paper

Use this:

**This project proposes a security-engineered adaptive hybrid image-encryption framework that combines image-bound key derivation, domain-separated subkeys, reversible transform-based scrambling, AES-GCM payload protection, authenticated metadata, and optional X25519 key exchange, with evaluation designed for honest comparison rather than exaggerated novelty claims.**
