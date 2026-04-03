# Future Changes Roadmap

Status snapshot as of 2026-04-02.

## Completed in the Current Codebase

These items are already implemented and available now.

- [x] Domain-separated key derivation (`K1..K4`)
- [x] Image-bound digest context (`SHA-256(image || shape || dtype)`)
- [x] Optional X25519 key-exchange modes
- [x] Nonce derivation hardening using dedicated nonce key (`K2`)
- [x] Metadata threat-model and claims-boundary fields
- [x] Single-image evaluation and ablation runner
- [x] Dataset-level batch attack simulation and HTML reporting
- [x] ML-backed adaptive layer using a finetuned Random Forest with heuristic fallback
- [x] Medical DICOM handling and PNG export for adaptive-model training
- [x] Finetuning report graphs and ML-backed pipeline rerun outputs

## Not Done Yet and Still Needed

These items are still open if the goal is a stronger publication.

- [ ] Multi-run benchmark harness with repeated runs and confidence intervals
- [ ] External baseline ingest for direct comparison with recent papers
- [ ] Formal security-game appendix or reduction-style claim mapping
- [ ] Reproducibility package with fixed seeds, environment lock file, and scripted reruns
- [ ] CPU/GPU runtime profiling for a scalability section
- [ ] Confidence-aware adaptive policy instead of simple threat overrides
- [ ] Stronger semantic/privacy features for the adaptive model
- [ ] Series-aware medical splitting or repeated cross-validation to avoid optimistic results

## Needed to Make This Stronger and More Defendable

- [ ] Compare the ML-backed adaptive pipeline against multiple recent hybrid image-encryption baselines
- [ ] Report repeated benchmark results, not only one held-out split
- [ ] Show ablation between heuristic adaptive mode and ML adaptive mode
- [ ] Tighten the adaptive claim boundary with confidence, fallback, and better labels
- [ ] Add a formal security-analysis section that maps every claim to a standard primitive
- [ ] Package the whole experiment so reviewers can rerun it easily
- [ ] Keep the chaos layer positioned as reversible preprocessing and diffusion, not as a new primitive

## Recommended Order of Next Work

If the goal is publication strength, the next work should be done in this order:

1. Add external baseline comparison tables.
2. Run repeated benchmark experiments with confidence intervals.
3. Add heuristic-vs-ML adaptive ablation and confidence-aware policy logic.
4. Improve the adaptive model with better labels and semantic/privacy features.
5. Write the formal security-analysis appendix.
6. Package reproducibility artifacts.
7. Add scalability profiling.

## Honest Status Summary

The core security-engineering work is done.

The ML adaptive layer is also now done in a practical, working form.

The publication-strength work that remains is mostly about broader comparison, stronger evaluation design, tighter adaptive-model analysis, and formal presentation. That means the project is now stronger than the earlier heuristic-only version, but it still needs benchmark depth and comparison discipline before making bigger paper claims.
