# Output Folders and Results Index

Date: 2026-04-02

This file explains the main output folders created during the Random Forest finetuning work and the new ML-backed pipeline evaluation.

## 1. Finetuning Model Output Folders

### `adaptive_rf_report/`

Purpose:

- main storage folder for trained Random Forest model files
- stores the converted medical PNG images used after DICOM export
- contains the first baseline finetuning run outputs

What it contains:

- `adaptive_random_forest.pkl`
  - first trained model from the small balanced run
- `adaptive_random_forest_cap100.pkl`
  - trained model from the `up_to_limit` cap-100 run
- `adaptive_random_forest_cap200.pkl`
  - trained model from the `up_to_limit` cap-200 run
- `confusion_matrix.csv`
  - confusion matrix for the first smaller run
- `feature_importances.csv`
  - feature importance values for the first smaller run
- `metrics.json`
  - metrics for the first smaller run
- `sample_manifest.csv`
  - train/test sample list for the first smaller run
- `medical_png_export/`
  - exported medical images converted from DICOM to PNG
  - current PNG count: `720`

What results this folder is for:

- baseline finetuning outputs
- medical DICOM conversion output
- final trained model storage

### `adaptive_rf_report_cap100/`

Purpose:

- stores the cap-100 finetuning experiment outputs

What it contains:

- `metrics.json`
  - holdout accuracy, CV score, train/test counts, sampled counts
- `sample_manifest.csv`
  - exact files used in train and test split
- `confusion_matrix.csv`
  - class-wise prediction matrix
- `feature_importances.csv`
  - most important model features
- `medical_export_failures.json`
  - malformed DICOM file list skipped during export

What results this folder is for:

- the larger finetuning run that used:
  - `100` faces
  - `50` forms
  - `100` land-scapes and others
  - `16` manga
  - `100` medical
- achieved about `95.65%` accuracy

### `adaptive_rf_report_cap200/`

Purpose:

- stores the best finetuning experiment outputs

What it contains:

- `metrics.json`
  - full summary for the best run
- `sample_manifest.csv`
  - exact train/test file list
- `confusion_matrix.csv`
  - class-wise evaluation matrix
- `feature_importances.csv`
  - top learned features

What results this folder is for:

- the best finetuning run that used:
  - `200` faces
  - `50` forms
  - `200` land-scapes and others
  - `16` manga
  - `200` medical
- achieved about `97.60%` holdout accuracy
- achieved about `98.45%` best CV score
- this run produced the model integrated into the pipeline

## 2. Finetuning Report and Graph Folder

### `adaptive_model_finetuning_report/`

Purpose:

- stores the graph outputs comparing the different finetuning runs

What it contains:

- `accuracy_curve.png`
  - accuracy and CV-score trend across finetuning runs
- `images_used_per_class.png`
  - number of images used from each class for each run
- `train_test_counts_best.png`
  - train/test image counts for the best run
- `confusion_matrix_best.png`
  - visual confusion matrix for the best run
- `per_class_metrics_best.png`
  - precision, recall, and F1 by class for the best run
- `feature_importance_best.png`
  - top feature importances for the best run
- `experiment_summary.csv`
  - compact summary table of the compared finetuning runs

What results this folder is for:

- presentation-ready finetuning graphs
- model-performance comparison across baseline, cap-100, and cap-200 runs

## 3. Held-Out Input Folder Used for the New Pipeline Test

### `pipeline_eval_input_ml_cap200_test/`

Purpose:

- stores the held-out `test` images copied from the best finetuning experiment
- used as the input set for the new ML-backed pipeline evaluation

What it contains:

- copied test images only
- current file count: `167`

What results this folder is for:

- controlled rerun input for the adaptive pipeline after ML integration

## 4. ML-Backed Pipeline Evaluation Output Folder

### `ml_pipeline_eval_run/`

Purpose:

- stores the full encryption/decryption outputs after integrating the trained Random Forest into the adaptive layer

What it contains:

- `passphrase_only/`
  - encrypted files and metadata for passphrase-only mode
  - current counts: `167` `.enc` files and `167` `.meta.json` files
- `x25519_only/`
  - encrypted files and metadata for public-key-only mode
  - current counts: `167` `.enc` files and `167` `.meta.json` files
- `hybrid/`
  - encrypted files and metadata for hybrid mode
  - current counts: `167` `.enc` files and `167` `.meta.json` files
- `keys/`
  - X25519 key files used by the batch evaluation
  - contains:
    - `recipient_private.pem`
    - `recipient_public.pem`
    - `wrong_private.pem`
    - `wrong_public.pem`
- `evaluation/`
  - aggregate JSON/CSV results and report folder

What results this folder is for:

- the full ML-backed pipeline rerun
- end-to-end encryption, decryption, attack simulation, tamper testing, and report generation

## 5. Pipeline Evaluation Summary Folder

### `ml_pipeline_eval_run/evaluation/`

Purpose:

- stores aggregate numerical results for the ML-backed pipeline rerun

What it contains:

- `batch_results.json`
  - full per-item and aggregate results
- `batch_results.csv`
  - flattened CSV version of per-item results
- `report/`
  - generated tables, graphs, and HTML summary

What results this folder is for:

- machine-readable evaluation output
- detailed record of the rerun metrics for all `501` pairs

## 6. Pipeline Evaluation Report Folder

### `ml_pipeline_eval_run/evaluation/report/`

Purpose:

- stores human-readable graphs and CSV summaries for the ML-backed pipeline rerun

Main files inside:

- `report.html`
  - full HTML summary report
- `dataset_summary.csv`
  - dataset counts
- `mode_summary.csv`
  - per-mode averages
- `sensitivity_counts.csv`
  - ML classifier sensitivity distribution
- `profile_counts.csv`
  - selected profile distribution
- `attack_success_rates.csv`
  - decrypt-success rates under attacks
- `attack_detection_rates.csv`
  - attack rejection/detection rates
- `metadata_tamper_success_rates.csv`
  - decrypt-success rates under metadata tampering
- `metadata_tamper_detection_rates.csv`
  - metadata tamper rejection rates

Main graphs inside:

- `mean_entropy.png`
- `mean_abs_corr.png`
- `mean_encrypt_time_ms.png`
- `mean_decrypt_time_ms.png`
- `mean_chosen_plaintext_npcr.png`
- `mean_chosen_plaintext_uaci.png`
- `box_encrypt_time_ms.png`
- `box_decrypt_time_ms.png`
- `box_cipher_entropy.png`
- `box_chosen_plaintext_npcr.png`
- `box_chosen_plaintext_uaci.png`
- `sensitivity_counts.png`
- `profile_counts.png`
- `sensitivity_share_pie.png`
- `profile_share_pie.png`
- `attack_detection_mean.png`
- `metadata_tamper_detection_mean.png`

What results this folder is for:

- final graphs and tables for the new pipeline rerun
- presentation/report-ready outputs showing:
  - exact reconstruction results
  - entropy and correlation behavior
  - chosen-plaintext NPCR and UACI
  - sensitivity/profile distribution under the ML classifier
  - ciphertext tamper rejection
  - metadata tamper rejection

## 7. Root-Level Markdown Result Files

These are not folders, but they explain the generated outputs:

- `ML_ADAPTIVE_MODEL_FINETUNING_REPORT.md`
  - written summary of the finetuning experiments and graphs
- `ML_ADAPTIVE_PIPELINE_RERUN_REPORT.md`
  - written summary of the new ML-backed pipeline evaluation
- `ATTACK_SIMULATION_AND_EVALUATION_REPORT.md`
  - written summary of the current ML-backed attack and tamper evaluation
- `ATTACKS_AND_GRAPH_EXPLANATION.md`
  - plain-language explanation of the current batch-report graphs and metrics

## 8. Legacy Reference Folder

### `artifacts/`

Purpose:

- keeps the older pre-ML batch outputs and single-image evaluation outputs that existed before the Random Forest adaptive layer was integrated

What it contains:

- the earlier `passphrase_only/`, `x25519_only/`, and `hybrid/` batch folders
- `artifacts/evaluation/` with the older aggregated batch report
- smoke-test and single-image evaluation artifacts

What results this folder is for:

- historical comparison with the earlier heuristic-era pipeline behavior
- legacy report references that were kept intentionally instead of being deleted

## 9. Quick Map

If you only need the most important places:

- best trained model:
  - `adaptive_rf_report/adaptive_random_forest_cap200.pkl`
- finetuning graphs:
  - `adaptive_model_finetuning_report/`
- held-out test input used for rerun:
  - `pipeline_eval_input_ml_cap200_test/`
- full rerun outputs:
  - `ml_pipeline_eval_run/`
- final pipeline graphs and report:
  - `ml_pipeline_eval_run/evaluation/report/`
