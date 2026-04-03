# Attacks and Graph Explanation Guide

Date: 2026-04-02

This file is a plain-language companion to `ATTACK_SIMULATION_AND_EVALUATION_REPORT.md`.
It explains:

- every implemented attack or tamper case
- what each graph in `ml_pipeline_eval_run/evaluation/report/` is showing
- what metrics such as entropy, NPCR, UACI, and correlation actually indicate

Legacy note:

- the older heuristic-era charts under `artifacts/evaluation/report/` are still in the workspace
- this guide now explains the newer ML-backed rerun under `ml_pipeline_eval_run/evaluation/report/`

## 1. Important Note

The implemented "attacks" in this repository are mostly tamper, corruption, replay, and credential-mismatch simulations.
They are meant to verify that the system rejects modified ciphertext or modified metadata.
They are not full cryptanalytic attacks against AES-GCM or the overall design.

So in this project:

- decryption failure under tampering is the correct secure behavior
- `0%` attack success is good
- `100%` detection or rejection is good

## 2. What Was Evaluated

Current batch summary from `ml_pipeline_eval_run/evaluation/report/`:

| Item | Current value |
| --- | ---: |
| Unique images | 167 |
| `passphrase_only` pairs | 167 |
| `x25519_only` pairs | 167 |
| `hybrid` pairs | 167 |
| Total pairs | 501 |

Current profile distribution:

| Profile | Count |
| --- | ---: |
| `max` | 114 |
| `lite` | 49 |
| `standard` | 4 |

Current sensitivity distribution:

| Sensitivity | Count |
| --- | ---: |
| `high` | 114 |
| `low` | 49 |
| `medium` | 4 |

The main difference from the old heuristic batch is that the ML-backed adaptive layer now drives most images into the `high` -> `max` path instead of the old `medium` -> `standard` path.

## 3. Attack-by-Attack Explanation

### 3.1 Ciphertext Corruption Attacks

These directly modify the encrypted payload bytes.

| Attack | What is changed | What it is trying to test | Secure result |
| --- | --- | --- | --- |
| Bit flip | One random bit in ciphertext is flipped | Whether even a tiny payload modification is detected | Decrypt should fail |
| Gaussian noise | Random numeric noise is added to ciphertext bytes | Whether many small byte-level distortions are detected | Decrypt should fail |
| Partial ciphertext loss, center | Only the middle `80%` of bytes is kept | Whether missing ciphertext bytes break integrity | Decrypt should fail |
| Partial ciphertext loss, head | Only the first `90%` of bytes is kept | Whether truncation at the end is detected | Decrypt should fail |
| Partial ciphertext loss, tail | Only the last `90%` of bytes is kept | Whether truncation at the beginning is detected | Decrypt should fail |
| Byte mutation | `16` random byte positions are replaced with random values | Whether larger byte corruption is detected | Decrypt should fail |
| Block shuffle | `16`-byte blocks are swapped around | Whether reordering ciphertext blocks is detected | Decrypt should fail |

What these mean in practice:

- the system should never silently output an image from altered ciphertext
- authenticated encryption should reject the payload before usable plaintext is returned

### 3.2 Replay and Substitution Attacks

These try to reuse data from another encrypted item.

| Attack | What is changed | What it is trying to test | Secure result |
| --- | --- | --- | --- |
| Replay by ciphertext swap | Metadata for one item is paired with ciphertext from another item | Whether ciphertext is bound tightly enough to its own metadata and key context | Decrypt should fail |
| Replay by metadata swap | Ciphertext for one item is paired with metadata from another item | Whether metadata reuse or substitution is detected | Decrypt should fail |

### 3.3 Credential Mismatch Attacks

These test access control rather than payload corruption.

| Attack | Applicable modes | What is changed | What it is trying to test | Secure result |
| --- | --- | --- | --- | --- |
| Wrong passphrase | `passphrase_only`, `hybrid` | Correct passphrase is changed by appending `#` | Whether passphrase-derived keys are enforced | Decrypt should fail |
| Wrong private key | `x25519_only`, `hybrid` | A different X25519 private key is used | Whether the wrong recipient key is rejected | Decrypt should fail |

### 3.4 Metadata Tamper Attacks

These modify the JSON metadata instead of the ciphertext.

| Tamper case | What is changed | Why it matters | Secure result |
| --- | --- | --- | --- |
| Missing metadata HMAC | `metadata_hmac` field is removed | Tests whether unsigned metadata is rejected | Decrypt should fail |
| Threat-level tamper | `threat_level` value is changed | Tests whether policy context is authenticated | Decrypt should fail |
| Profile-round tamper | `profile.permutation_rounds` is incremented | Tests whether transform settings are authenticated | Decrypt should fail |
| Nonce-salt tamper | `nonce_salt_b64` is altered | Tests whether nonce derivation context is protected | Decrypt should fail |
| Extra-field injection | `evil_extra_field` is added | Tests whether unauthorized metadata extension is rejected | Decrypt should fail |
| Salt tamper | `salt_b64` is altered | Tests whether KDF inputs are protected | Decrypt should fail |
| Image-digest tamper | `image_sha256_b64` is altered | Tests whether image binding is protected | Decrypt should fail |
| Working-shape tamper | `working_shape` is changed | Tests whether reconstruction dimensions are authenticated | Decrypt should fail |
| Dtype tamper | `dtype` is switched | Tests whether array type metadata is protected | Decrypt should fail |
| Chaos-seed tamper | `chaos_seed` is incremented | Tests whether transform seed data is authenticated | Decrypt should fail |

### 3.5 Chosen-Plaintext Differential Test

This is not a tamper attack. It is a diffusion test.

Procedure:

1. Take the original image.
2. Change one pixel by `+1 mod 256`.
3. Re-encrypt with the same salts and same key context.
4. Compare the two ciphertexts using NPCR and UACI.

Why this is useful:

- it measures how strongly a tiny plaintext change spreads through the ciphertext
- strong diffusion means a very small plaintext change causes a very large ciphertext change

## 4. What the Key Metrics Mean

| Metric | What it means | Good direction | How to interpret current results |
| --- | --- | --- | --- |
| `exact_match` | Whether decrypted image exactly equals original image | higher | `1.0` means all clean decryptions were exact |
| `PSNR` | Reconstruction quality compared with original | higher | `inf` means no reconstruction error |
| `MSE` | Average squared reconstruction error | lower | `0` means perfect reconstruction |
| `encrypt_time_ms` | Encryption runtime | lower | performance metric, not a direct security metric |
| `decrypt_time_ms` | Decryption runtime | lower | performance metric, not a direct security metric |
| `cipher_entropy` | Randomness of ciphertext byte values | near `8` | for byte data, `8` is the theoretical maximum |
| `cipher_adj_corr` | Correlation between neighboring ciphertext bytes | near `0` | close to zero means adjacent bytes are not predictably related |
| `NPCR` | Percentage of ciphertext byte positions that changed after a tiny plaintext change | higher | high value means strong diffusion |
| `UACI` | Average size of byte-value change after a tiny plaintext change | moderate-high | around one-third of full scale is commonly considered strong |
| Attack success rate | Fraction of tampered cases that still decrypted | lower | `0%` is ideal here |
| Detection rate | Fraction of tampered cases that were rejected | higher | `100%` is ideal here |

## 5. What Entropy Indicates

Entropy here means Shannon entropy over ciphertext byte values.

Simple meaning:

- low entropy means the byte distribution is more predictable or structured
- high entropy means the byte distribution is more uniform and random-looking

For ciphertext bytes:

- maximum entropy is `8` bits per byte
- values very close to `8` suggest the ciphertext does not show an obvious biased byte distribution

Current values:

| Mode | Mean ciphertext entropy |
| --- | ---: |
| `passphrase_only` | `7.99952515` |
| `x25519_only` | `7.99952895` |
| `hybrid` | `7.99952735` |

Interpretation:

- these values are extremely close to the ideal byte-level maximum
- that indicates the ciphertext bytes look highly random in distribution
- entropy alone is a good sign, but it does not prove security by itself

## 6. What Correlation Indicates

Adjacent correlation checks whether neighboring ciphertext bytes still move together in a predictable way.

Simple meaning:

- high positive correlation means nearby bytes still resemble each other structurally
- value near `0` means neighboring bytes behave almost independently

Current mean absolute adjacent correlation:

| Mode | Mean abs correlation |
| --- | ---: |
| `passphrase_only` | `0.00101817` |
| `x25519_only` | `0.00113619` |
| `hybrid` | `0.00103332` |

Interpretation:

- all values are extremely close to zero
- this means local byte-to-byte structure is effectively removed in the ciphertext

## 7. What NPCR and UACI Indicate

### 7.1 NPCR

NPCR stands for Number of Pixel Change Rate. In this repository it is applied to ciphertext-byte arrays.

Simple meaning:

- if one tiny plaintext change causes almost all ciphertext positions to change, NPCR will be very high
- high NPCR means strong avalanche or diffusion behavior

Current mean NPCR:

| Mode | Mean NPCR (%) |
| --- | ---: |
| `passphrase_only` | `99.60997049` |
| `x25519_only` | `99.60956916` |
| `hybrid` | `99.60935988` |

Interpretation:

- roughly `99.6%` of ciphertext byte positions changed after a one-pixel plaintext change
- that is strong diffusion

### 7.2 UACI

UACI stands for Unified Average Changing Intensity.

Simple meaning:

- NPCR tells you how many positions changed
- UACI tells you how much they changed on average

Current mean UACI:

| Mode | Mean UACI (%) |
| --- | ---: |
| `passphrase_only` | `33.46355794` |
| `x25519_only` | `33.45832840` |
| `hybrid` | `33.46241902` |

Interpretation:

- the changed bytes are not only changing position-wise
- they are also changing by substantial average magnitude
- values around `33%` are commonly treated as strong for image-encryption diffusion analysis

## 8. How to Read the Boxplots

The files starting with `box_` are boxplots.

What a boxplot shows:

- center line: median
- box: middle `50%` of values
- whiskers: spread outside the middle range
- compact box: stable metric with low variability
- wide box: more variability across images

How to interpret these in this project:

- narrow runtime boxes mean encryption or decryption time is stable across the dataset
- narrow entropy, NPCR, or UACI boxes mean the security metric is consistent across images

## 9. Graph-by-Graph Explanation

### 9.1 Dataset and Distribution Artifacts

| Graph or table | What it shows | How to read it | Current takeaway |
| --- | --- | --- | --- |
| `dataset_summary_table.png` | Overall dataset counts | Read unique images and total per-mode pairs | `167` unique images and `501` total pairs were evaluated |
| `mode_summary_table.png` | Main per-mode averages | Compare accuracy, timings, entropy, correlation, NPCR, and UACI across modes | All three modes achieved exact reconstruction with very similar security statistics |
| `unique_images_table.png` | Preview table of unique inputs and selected profiles | Use it to inspect which image got which sensitivity label and profile | Most images are now in the `high` / `max` path |
| `sensitivity_counts.png` | Bar chart of sensitivity labels | Taller bars mean more images in that class | `high` dominates the current rerun |
| `sensitivity_share_pie.png` | Pie chart of sensitivity proportions | Larger slices mean larger class share | Most of the held-out rerun images were classified as `high` |
| `profile_counts.png` | Bar chart of selected profiles | Shows how often each adaptive profile was chosen | `max` dominates profile selection |
| `profile_share_pie.png` | Pie chart of profile proportions | Larger slice means more images used that profile | `max` is the main operating profile in the current batch |
| `sensitivity_profile_crosstab_table.png` | Sensitivity-to-profile mapping table | Read each row to see which profile each sensitivity produced | `low -> lite`, `medium -> standard`, `high -> max` |

### 9.2 Security Metric Bar Charts

| Graph | What it shows | How to read it | Current takeaway |
| --- | --- | --- | --- |
| `mean_entropy.png` | Mean ciphertext entropy per mode | Higher and closer to `8` is better | All modes are essentially ideal at about `7.99953` |
| `mean_abs_corr.png` | Mean absolute adjacent byte correlation per mode | Lower and closer to `0` is better | All modes are near zero, so local ciphertext structure is suppressed |
| `mean_encrypt_time_ms.png` | Mean encryption time per mode | Lower bars mean faster encryption | `x25519_only` is fastest in this rerun |
| `mean_decrypt_time_ms.png` | Mean decryption time per mode | Lower bars mean faster decryption | `x25519_only` is fastest here too |
| `mean_chosen_plaintext_npcr.png` | Mean NPCR after one-pixel change | Higher means stronger diffusion | All modes are around `99.609%` |
| `mean_chosen_plaintext_uaci.png` | Mean UACI after one-pixel change | Moderate-high values indicate strong diffusion magnitude | All modes are around `33.46%` |

### 9.3 Attack Outcome Artifacts

| Graph or table | What it shows | How to read it | Current takeaway |
| --- | --- | --- | --- |
| `attack_success_rates_table.png` | Per-mode decrypt-success rates under implemented attack cases | Lower is better; `0.0` means the tampered case did not decrypt | Every implemented ciphertext, replay, and credential attack was rejected |
| `attack_detection_mean.png` | Mean attack detection rate by mode | Higher is better; `100%` is ideal | All modes show `100%` mean detection |
| `metadata_tamper_success_rates_table.png` | Per-mode decrypt-success rates for metadata tamper cases | Lower is better; `0.0` means metadata tamper did not decrypt | Every implemented metadata tamper case was rejected |
| `metadata_tamper_detection_mean.png` | Mean metadata tamper detection rate by mode | Higher is better | All modes show `100%` mean metadata tamper detection |

### 9.4 Boxplots

| Graph | What it shows | How to read it | Current takeaway |
| --- | --- | --- | --- |
| `box_encrypt_time_ms.png` | Distribution of encryption times by mode | Compare medians and box widths | Runtime is stable enough to compare across modes |
| `box_decrypt_time_ms.png` | Distribution of decryption times by mode | Lower median and tighter spread are better for consistency | Decryption cost is similarly stable |
| `box_cipher_entropy.png` | Distribution of ciphertext entropy values | Values clustered near `8` are desirable | Entropy remains consistently high across images |
| `box_chosen_plaintext_npcr.png` | Distribution of NPCR across images | Tight, high boxes mean stable strong diffusion | NPCR is both high and consistent |
| `box_chosen_plaintext_uaci.png` | Distribution of UACI across images | Stable mid-30% range is desirable | UACI is consistent across the dataset |

## 10. Quick Reading of the Current Results

If someone asks, "What do the graphs say overall?", the short answer is:

- clean decryption worked perfectly in all three modes
- ciphertext entropy is almost exactly the ideal byte-level value of `8`
- adjacent ciphertext correlation is essentially zero
- one-pixel plaintext changes produce very large ciphertext changes, shown by NPCR around `99.6%` and UACI around `33.46%`
- every implemented ciphertext tamper, replay case, credential mismatch, and metadata tamper was rejected in the current run
- most observed behavior now reflects the `max` profile because the ML-backed adaptive layer classifies most of this held-out set as `high`

## 11. What These Graphs Do Not Prove

These graphs support strong engineering claims, but they do not prove everything.

They do support:

- strong tamper detection
- correct reversibility on untampered inputs
- strong ciphertext randomness indicators
- strong diffusion under the implemented chosen-plaintext test

They do not by themselves prove:

- security against every advanced cryptanalytic strategy
- security under every deployment mistake
- graceful recovery after ciphertext corruption
- superiority over all published image-encryption systems

## 12. One-Sentence Interpretation

The current ML-backed rerun graphs indicate that the pipeline behaves like an authenticated, reversible image-encryption system with strong tamper rejection, high ciphertext randomness, very low local correlation, and strong diffusion under small plaintext changes, even after replacing the old heuristic adaptive layer with the finetuned Random Forest model.
