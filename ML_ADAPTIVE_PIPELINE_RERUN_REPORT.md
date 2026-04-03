# ML Adaptive Pipeline Rerun Report

Date: 2026-04-02

This report summarizes the new batch evaluation after integrating the finetuned Random Forest adaptive classifier into the pipeline.

## 1. Evaluation Setup

The rerun used the held-out `test` split from the best finetuning experiment (`adaptive_rf_report_cap200`).

| Item | Value |
| --- | ---: |
| Input folder | `pipeline_eval_input_ml_cap200_test` |
| Unique images evaluated | `167` |
| Modes | `passphrase_only`, `x25519_only`, `hybrid` |
| Total encryption-decryption pairs | `501` |
| Threat level | `balanced` |
| Chosen-plaintext differential test | enabled |
| Output root | `ml_pipeline_eval_run` |

Generated aggregate report:

- `ml_pipeline_eval_run/evaluation/report/report.html`

## 2. Adaptive Classification Distribution

The ML-backed classifier produced the following sensitivity distribution on the held-out set:

| Sensitivity | Count |
| --- | ---: |
| `high` | `114` |
| `low` | `49` |
| `medium` | `4` |

Selected profile distribution:

| Profile | Count |
| --- | ---: |
| `max` | `114` |
| `lite` | `49` |
| `standard` | `4` |

This shows the new classifier is no longer collapsing most images into the middle tier. It is making stronger high/low decisions for the held-out set.

## 3. Mode Summary

| Mode | Count | Exact match rate | Mean encrypt time (ms) | Mean decrypt time (ms) | Mean entropy | Mean abs corr | Mean NPCR (%) | Mean UACI (%) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `passphrase_only` | `167` | `1.0` | `333.769953` | `327.995972` | `7.999525` | `0.001018` | `99.609970` | `33.463558` |
| `x25519_only` | `167` | `1.0` | `271.215451` | `274.895810` | `7.999529` | `0.001136` | `99.609569` | `33.458328` |
| `hybrid` | `167` | `1.0` | `320.770219` | `329.241796` | `7.999527` | `0.001033` | `99.609360` | `33.462419` |

Interpretation:

- all untampered decryptions remained exact
- entropy stayed near the ideal byte-level maximum
- adjacent correlation stayed near zero
- NPCR and UACI remained strong and stable

## 4. Attack and Tamper Results

Universal ciphertext, replay, credential mismatch, and metadata tamper cases all remained fully rejected in the rerun.

Attack decrypt-success rates:

- all values in `ml_pipeline_eval_run/evaluation/report/attack_success_rates.csv` are `0.0`

Metadata tamper decrypt-success rates:

- all values in `ml_pipeline_eval_run/evaluation/report/metadata_tamper_success_rates.csv` are `0.0`

That means:

- ciphertext tampering was still detected
- replay and substitution were still rejected
- credential mismatch still failed
- metadata tampering was still rejected

## 5. ML Integration Confirmation

The new metadata now stores Random Forest classification outputs directly.

Example fields now present in metadata:

- `classifier_source: "random_forest"`
- `predicted_class`
- `confidence`
- `p_low`, `p_medium`, `p_high`
- class probabilities such as `class_prob__faces`
- `model_path`

This confirms the rerun was executed with the finetuned ML-backed adaptive layer rather than the old heuristic-only classifier.

## 6. Overall Conclusion

The finetuned Random Forest adaptive layer was successfully integrated into the pipeline and the full rerun preserved the important cryptographic and engineering outcomes:

- exact lossless reconstruction on untampered inputs
- strong ciphertext randomness and diffusion metrics
- full rejection of the implemented tamper and replay cases
- richer adaptive decisions, with the model assigning many images to `high/max` and `low/lite` instead of defaulting mostly to `medium/standard`
