# Attack Simulation and Evaluation Report

Date: 2026-04-02

## 1. Report Objective

This document summarizes the current dataset-level attack simulation and evaluation work in the repository after the ML-backed adaptive layer was integrated into the pipeline.

It explains:

- what was tested
- how each attack or tamper case was simulated
- which metrics were collected
- what the current ML-backed rerun shows
- what these results do and do not prove

This report now reflects the latest rerun under:

- `batch_run.py`
- `evaluation/attacks.py`
- `ml_pipeline_eval_run/evaluation/batch_results.json`
- `ml_pipeline_eval_run/evaluation/report/*.csv`

Legacy note:

- the earlier heuristic-era batch outputs under `artifacts/` are still kept in the workspace as historical reference
- this document is about the newer ML-backed rerun

## 2. Claim Boundary

This project should be described as a security-engineered hybrid image-protection framework, not as a new cryptographic primitive.

The current attack simulation primarily validates:

- tamper detection
- credential mismatch rejection
- replay and substitution rejection
- metadata integrity enforcement
- differential behavior under small plaintext changes
- reproducible dataset-level evaluation across three operating modes

It does **not** by itself prove:

- resistance to all forms of cryptanalysis
- superiority over every published image-encryption scheme
- graceful recovery after ciphertext damage

This distinction matters because AES-GCM is expected to reject modified ciphertext instead of trying to recover partial plaintext.

## 3. Evidence Base and Files Used

### Core implementation files

- `batch_run.py`
  - batch encryption in three modes
  - attack simulation over all generated pairs
  - aggregate JSON and CSV generation
- `evaluation/attacks.py`
  - helper functions for ciphertext perturbation and corruption
- `adaptive/classifier.py`
  - ML-first Random Forest sensitivity classifier with heuristic fallback
- `pipeline/encrypt.py`
  - adaptive encryption pipeline
- `pipeline/decrypt.py`
  - adaptive decryption pipeline
- `crypto/metadata_auth.py`
  - metadata HMAC verification path

### Result files used in this report

- `ml_pipeline_eval_run/evaluation/batch_results.json`
- `ml_pipeline_eval_run/evaluation/report/mode_summary.csv`
- `ml_pipeline_eval_run/evaluation/report/attack_success_rates.csv`
- `ml_pipeline_eval_run/evaluation/report/metadata_tamper_success_rates.csv`
- `ml_pipeline_eval_run/evaluation/report/dataset_summary.csv`
- `ml_pipeline_eval_run/evaluation/report/profile_counts.csv`
- `ml_pipeline_eval_run/evaluation/report/sensitivity_counts.csv`
- `ml_pipeline_eval_run/evaluation/report/sensitivity_profile_crosstab.csv`

## 4. Experiment Configuration

The latest dataset-level rerun was executed with the following configuration:

| Item | Value |
| --- | --- |
| Input dataset | `pipeline_eval_input_ml_cap200_test` |
| Input origin | held-out `test` split copied from `adaptive_rf_report_cap200/sample_manifest.csv` |
| Unique images processed | 167 |
| Total evaluated encryption-decryption pairs | 501 |
| Operating modes | `passphrase_only`, `x25519_only`, `hybrid` |
| Threat level | `balanced` |
| Chosen-plaintext differential test | enabled |
| Output root | `ml_pipeline_eval_run/` |
| Aggregated evaluation folder | `ml_pipeline_eval_run/evaluation/` |

The `hybrid` output folder corresponds to metadata key mode `hybrid_passphrase_x25519`.

## 5. System Under Evaluation

The evaluated system follows this security-engineering pipeline:

1. Classify image sensitivity using the finetuned Random Forest adaptive classifier.
2. Fall back to the heuristic classifier only if the model is unavailable.
3. Select an adaptive profile based on sensitivity plus threat level.
4. Compute an image-bound digest.
5. Derive master key material from passphrase and/or X25519 shared secret plus image digest and salt.
6. Expand into domain-separated keys for:
   - AES-GCM payload encryption
   - nonce derivation
   - chaos/permutation seed derivation
   - metadata HMAC authentication
7. Apply reversible transform steps:
   - optional Arnold map
   - keyed permutation
8. Encrypt with AES-256-GCM.
9. Save authenticated metadata with HMAC-SHA256.

The current ML-backed pipeline loads:

- `adaptive_rf_report/adaptive_random_forest_cap200.pkl`

This means the current attack simulation is validating both the cryptographic path and the current adaptive decision path used in production metadata.

## 6. Adaptive Profile Distribution in the Current Batch

Under the current `balanced` threat setting, the 167 unique images were distributed as follows:

| Sensitivity label | Count |
| --- | ---: |
| `high` | 114 |
| `low` | 49 |
| `medium` | 4 |

| Selected profile | Count |
| --- | ---: |
| `max` | 114 |
| `lite` | 49 |
| `standard` | 4 |

Cross-tab result:

| Sensitivity | Selected profile |
| --- | --- |
| `low` | always `lite` |
| `medium` | always `standard` |
| `high` | always `max` |

Interpretation:

- the ML-backed rerun is dominated by `high` sensitivity and therefore by the `max` profile
- this is very different from the older heuristic-era batch, which was mostly `standard`
- the current timing and attack outcomes therefore mostly reflect the `max` configuration rather than the old middle-tier configuration

## 7. Attack Simulation Design

### 7.1 Ciphertext Corruption and Integrity Tests

The batch evaluator simulates the following direct payload tamper cases:

| Attack case | Simulation method | Parameters |
| --- | --- | --- |
| Bit flip | flip one random bit in ciphertext | fixed seed `11` |
| Gaussian noise | add noise over ciphertext bytes treated as `uint8` | `sigma = 8.0`, seed `23` |
| Partial ciphertext loss, center | keep only the center slice | keep ratio `0.8` |
| Partial ciphertext loss, head | keep only the front slice | keep ratio `0.9` |
| Partial ciphertext loss, tail | keep only the end slice | keep ratio `0.9` |
| Byte mutation | replace random byte positions with random values | `16` bytes, seed `29` |
| Block shuffle | swap ciphertext blocks while preserving total length | block size `16`, swaps `4`, seed `31` |

Expected secure behavior:

- AES-GCM authentication should fail
- decryption should be rejected
- the system should not silently output a modified image

### 7.2 Replay and Substitution Tests

The batch evaluator also tests substitution attacks:

| Attack case | Simulation method |
| --- | --- |
| Replay by ciphertext swap | decrypt current metadata with ciphertext from another item in the same mode |
| Replay by metadata swap | decrypt current ciphertext with metadata from another item in the same mode |

Expected secure behavior:

- mismatch between ciphertext, nonce context, image binding, or metadata authentication should cause rejection

### 7.3 Credential Mismatch Tests

Two negative authentication tests are included:

| Attack case | Applicable modes | Simulation method |
| --- | --- | --- |
| Wrong passphrase | `passphrase_only`, `hybrid` | append `#` to the correct passphrase |
| Wrong private key | `x25519_only`, `hybrid` | use a different generated X25519 private key |

Expected secure behavior:

- incorrect credentials should never decrypt successfully

### 7.4 Metadata Tamper Tests

The metadata authentication suite simulates ten tamper conditions:

| Tamper case | Simulation method |
| --- | --- |
| Missing metadata HMAC | remove `metadata_hmac` field |
| Threat-level tamper | change `threat_level` |
| Profile-round tamper | increment `profile.permutation_rounds` |
| Nonce-salt tamper | alter `nonce_salt_b64` |
| Extra-field injection | add `evil_extra_field` |
| Salt tamper | alter `salt_b64` |
| Image-digest tamper | alter `image_sha256_b64` |
| Working-shape tamper | change `working_shape` |
| Dtype tamper | switch `dtype` |
| Chaos-seed tamper | increment `chaos_seed` |

Expected secure behavior:

- metadata HMAC verification or dependent decryption checks should fail

### 7.5 Chosen-Plaintext Differential Test

The batch evaluator includes a controlled one-pixel chosen-plaintext experiment:

1. Take the original input image.
2. Change pixel `[0, 0, 0]` by `+1 mod 256`.
3. Re-encrypt using:
   - the same profile
   - the same salt
   - the same nonce salt
   - the same shared-secret context when applicable
4. Compare original ciphertext and perturbed-image ciphertext using:
   - NPCR
   - UACI

Reason for fixing the salts and context:

- it isolates ciphertext sensitivity to the plaintext change instead of mixing in fresh randomness

### 7.6 Important Interpretation Note

These attack functions are perturbation and tamper-detection tools. They are not cryptanalytic attacks in the strict academic sense. A failed decryption under tampering is the correct result for AES-GCM and authenticated metadata.

## 8. Evaluation Metrics

The current batch run records the following metrics:

| Metric | Meaning | Desired interpretation |
| --- | --- | --- |
| `exact_match` | whether decrypted image matches original exactly | higher is better |
| `PSNR` | distortion between original and decrypted image | infinite indicates perfect recovery |
| `MSE` | reconstruction error | lower is better, ideally `0` |
| `encrypt_time_ms` | encryption runtime | lower is better |
| `decrypt_time_ms` | decryption runtime | lower is better |
| `cipher_entropy` | randomness of ciphertext byte distribution | should be close to `8` for byte data |
| `cipher_adj_corr` | adjacent correlation in ciphertext bytes | should be close to `0` |
| `chosen_plaintext_npcr` | percentage of byte positions changed after tiny plaintext change | higher is better |
| `chosen_plaintext_uaci` | average intensity difference after tiny plaintext change | moderate-high diffusion indicator |
| Attack decrypt-success rate | proportion of tampered inputs that still decrypted | lower is better |
| Metadata tamper success rate | proportion of tampered metadata cases that still decrypted | lower is better |

## 9. Aggregate Evaluation Results

### 9.1 Dataset Summary

| Metric | Value |
| --- | ---: |
| Unique images | 167 |
| Pairs in `passphrase_only` | 167 |
| Pairs in `x25519_only` | 167 |
| Pairs in `hybrid` | 167 |
| Total evaluated pairs | 501 |
| Total generated output files estimate | 1002 |

### 9.2 Untampered Reconstruction Outcome

Current untampered reconstruction results across all 501 pairs:

- successful decryptions: `501 / 501`
- exact matches: `501 / 501`
- exact match rate: `1.0` in all modes

Interpretation:

- the pipeline preserved full reversibility for all untampered cases in the current ML-backed batch

### 9.3 Mode-Wise Performance and Security Metrics

| Mode | Pairs | Exact match rate | Mean encrypt time (ms) | Mean decrypt time (ms) | Mean ciphertext entropy | Mean abs adjacent correlation | Mean NPCR (%) | Mean UACI (%) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `passphrase_only` | 167 | 100.00 | 333.77 | 328.00 | 7.999525 | 0.001018 | 99.609970 | 33.463558 |
| `x25519_only` | 167 | 100.00 | 271.22 | 274.90 | 7.999529 | 0.001136 | 99.609569 | 33.458328 |
| `hybrid` | 167 | 100.00 | 320.77 | 329.24 | 7.999527 | 0.001033 | 99.609360 | 33.462419 |

Observations:

- all three modes achieved perfect reconstruction on untampered inputs
- ciphertext entropy remains extremely close to the byte-level maximum in every mode
- ciphertext adjacent correlation remains extremely close to zero
- chosen-plaintext NPCR and UACI remain highly stable across all three modes
- in this rerun, `x25519_only` is still the fastest mode on average
- the adaptive-layer upgrade did not break reversibility, metadata integrity, or diffusion behavior

## 10. Attack Simulation Outcomes

### 10.1 Total Negative-Path Checks Executed

Across the 501 evaluated pairs, the current batch exercised `10,187` applicable negative-path checks:

- `4,509` universal ciphertext and replay checks
  - `9` cases x `501` pairs
- `334` wrong-passphrase checks
  - only for `passphrase_only` and `hybrid`
- `334` wrong-private-key checks
  - only for `x25519_only` and `hybrid`
- `5,010` metadata tamper checks
  - `10` cases x `501` pairs

Result:

- no applicable negative-path check produced a successful decrypt

### 10.2 Universal Ciphertext and Replay Attacks

These cases were exercised for all 501 pairs:

| Attack case | Successful decrypts | Success rate | Detection/rejection rate |
| --- | ---: | ---: | ---: |
| Bit flip | 0 / 501 | 0.00% | 100.00% |
| Gaussian noise | 0 / 501 | 0.00% | 100.00% |
| Partial ciphertext loss, center 0.8 | 0 / 501 | 0.00% | 100.00% |
| Partial ciphertext loss, head 0.9 | 0 / 501 | 0.00% | 100.00% |
| Partial ciphertext loss, tail 0.9 | 0 / 501 | 0.00% | 100.00% |
| Byte mutation | 0 / 501 | 0.00% | 100.00% |
| Block shuffle | 0 / 501 | 0.00% | 100.00% |
| Replay by ciphertext swap | 0 / 501 | 0.00% | 100.00% |
| Replay by metadata swap | 0 / 501 | 0.00% | 100.00% |

### 10.3 Credential Mismatch Attacks

These cases are mode-specific:

| Attack case | Applicable checks | Successful decrypts | Success rate | Detection/rejection rate |
| --- | ---: | ---: | ---: | ---: |
| Wrong passphrase | 334 | 0 / 334 | 0.00% | 100.00% |
| Wrong private key | 334 | 0 / 334 | 0.00% | 100.00% |

Interpretation:

- passphrase-based access control worked for all tested passphrase modes
- X25519-based access control worked for all tested public-key modes

### 10.4 Metadata Tamper Attacks

Each metadata tamper case was exercised for all 501 pairs:

| Metadata tamper case | Successful decrypts | Success rate | Detection/rejection rate |
| --- | ---: | ---: | ---: |
| Missing metadata HMAC | 0 / 501 | 0.00% | 100.00% |
| Threat-level tamper | 0 / 501 | 0.00% | 100.00% |
| Profile-round tamper | 0 / 501 | 0.00% | 100.00% |
| Nonce-salt tamper | 0 / 501 | 0.00% | 100.00% |
| Extra-field injection | 0 / 501 | 0.00% | 100.00% |
| Salt tamper | 0 / 501 | 0.00% | 100.00% |
| Image-digest tamper | 0 / 501 | 0.00% | 100.00% |
| Working-shape tamper | 0 / 501 | 0.00% | 100.00% |
| Dtype tamper | 0 / 501 | 0.00% | 100.00% |
| Chaos-seed tamper | 0 / 501 | 0.00% | 100.00% |

Interpretation:

- metadata authentication is functioning as intended in the current experiment
- the implementation does not silently accept modified operational parameters

## 11. What the Current Results Mean

### 11.1 Integrity and Tamper Detection

The strongest conclusion from the current attack simulation is:

- the system consistently rejects tampered ciphertext
- the system consistently rejects altered metadata
- the system consistently rejects replay and substitution attempts
- the system consistently rejects incorrect credentials

This is exactly what should happen when:

- AES-GCM is used correctly
- metadata is HMAC-authenticated
- nonce and key derivation are bound to the correct context

### 11.2 Differential Behavior

The chosen-plaintext NPCR and UACI values are stable across all three modes:

- NPCR is approximately `99.609%`
- UACI is approximately `33.46%`

Interpretation:

- a one-pixel plaintext change causes a large ciphertext difference
- the transform plus AES pipeline is not showing weak local sensitivity in the current setup

### 11.3 Reversibility and Correctness

Because all untampered decryptions matched exactly:

- the transform stage is reversible
- metadata carries enough valid reconstruction information
- adaptive profile selection is not breaking decryption correctness
- ML-backed classification is not breaking decryption correctness

### 11.4 Runtime Interpretation

The timing results show:

- all three modes are operationally usable for batch testing
- the additional key-exchange flexibility does not create a catastrophic runtime increase
- the ML-backed adaptive layer did not make the batch pipeline operationally unstable

## 12. Limitations of the Current Evaluation

The current report is strong for implementation validation, but it still has clear limits:

1. The rerun input is a held-out split derived from the local training dataset, not yet a formal public benchmark such as Kodak or USC-SIPI.
2. The current batch was run only under the `balanced` threat level.
3. The current rerun is a single held-out split, not repeated cross-validation or repeated benchmark sampling.
4. The attack simulations validate detection and rejection behavior, not recovery after corruption.
5. The results do not replace formal cryptanalysis.
6. Timing values are environment-dependent and should not be treated as universal constants.
7. The current batch report does not yet automate comparison against external published baselines.

## 13. Reproducibility

The current ML-backed dataset-level experiment can be reproduced with:

```powershell
python batch_run.py pipeline_eval_input_ml_cap200_test `
  --out-dir ml_pipeline_eval_run `
  --count 167 `
  --passphrase "codex-demo-passphrase" `
  --threat balanced `
  --report `
  --overwrite
```

Outputs of interest:

- `ml_pipeline_eval_run/evaluation/batch_results.json`
- `ml_pipeline_eval_run/evaluation/batch_results.csv`
- `ml_pipeline_eval_run/evaluation/report/report.html`
- `ml_pipeline_eval_run/evaluation/report/mode_summary.csv`
- `ml_pipeline_eval_run/evaluation/report/attack_success_rates.csv`
- `ml_pipeline_eval_run/evaluation/report/metadata_tamper_success_rates.csv`

For single-image ablation with deeper attack sweeps, the repository also provides:

```powershell
python evaluate_pipeline.py <image_path> `
  --passphrase "p@ss" `
  --out-dir artifacts/eval_single `
  --attack-suite high `
  --report
```

That path is useful for:

- `aes_only` vs `static_chaos_aes` vs `proposed_hardened`
- deeper sweep curves for bit flips, byte mutation, truncation, block shuffling, and noise

## 14. Final Conclusion

Based on the current implementation and generated ML-backed rerun artifacts, the attack simulation and evaluation work can be summarized as follows:

- the project successfully executed a 167-image, 501-pair batch evaluation across three operating modes
- all untampered decryptions were exact and lossless
- ciphertext statistical behavior is strong, with entropy near `8` and adjacent correlation near `0`
- chosen-plaintext sensitivity is strong and consistent across modes
- every implemented attack, replay case, credential mismatch, and metadata tamper case was rejected in the current experiment
- metadata authentication is working effectively and prevents silent parameter manipulation
- integrating the finetuned Random Forest adaptive layer did not weaken the cryptographic or engineering results

The strongest defensible claim from the present evidence is:

> the current framework behaves like a well-engineered authenticated image-encryption pipeline with ML-backed adaptive profile selection, strong tamper detection, correct reversibility, and reproducible multi-mode evaluation.

That is a solid project result and a stronger basis for report writing, paper drafting, and future baseline comparison than the earlier heuristic-only batch run.
