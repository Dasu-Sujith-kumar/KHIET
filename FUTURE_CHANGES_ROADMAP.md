# Future Changes Roadmap

Status snapshot as of 2026-03-08.

## Completed in the Current Codebase

These items are already implemented and available in the project.

- [x] Domain-separated key derivation (`K1..K4`)
- [x] Image-bound digest context (`SHA-256(image || shape || dtype)`)
- [x] Optional X25519 key-exchange modes
- [x] Nonce derivation hardening using dedicated nonce key (`K2`)
- [x] Metadata threat-model and claims-boundary fields
- [x] Evaluation and ablation runner with attack simulations

## Not Done Yet and Still Needed

These items are not completed yet and are still needed if the goal is a stronger publication.

- [ ] Multi-image benchmark harness with repeated runs and confidence intervals
- [ ] External baseline ingest for direct comparison with 3-5 recent papers
- [ ] Formal security-game appendix draft (for example, IND-CCA style mapping)
- [ ] Reproducibility package with fixed seeds, dataset manifest, and environment lock file
- [ ] CPU/GPU runtime profiling for a scalability section

## Needed to Make This Strong and Publishable

These are the concrete gaps that still separate the current project from a stronger paper.

- [ ] Run evaluation on a real benchmark set instead of only smoke-style examples
- [ ] Compare against multiple recent hybrid image-encryption baselines in one reproducible table
- [ ] Add a clear formal security-analysis section that maps every claim to a standard primitive
- [ ] Upgrade the adaptive layer if the paper wants to claim meaningful AI assistance
- [ ] Add reproducible experiment packaging so reviewers can repeat the results
- [ ] Add a paper-ready narrative explaining what the chaos layer does and does not contribute
- [ ] Document limitations honestly so the work is framed as security engineering, not a new cipher claim

## Recommended Order of Next Work

If the goal is publication strength, the next work should be done in this order:

1. Build the multi-image benchmark harness.
2. Add external baseline comparison tables.
3. Write the formal security-analysis appendix.
4. Strengthen the adaptive layer or narrow its claim boundary.
5. Package reproducibility artifacts.
6. Add scalability profiling.
7. Convert the results into a paper-ready comparison and limitations section.

## Honest Status Summary

The core security-engineering hardening work is done.

The publication-strength work is not done yet.

That means the project is already strong as an implementation, but still needs broader evaluation, stronger comparison, clearer claim boundaries, and more formal analysis before it can be positioned as a stronger paper.
