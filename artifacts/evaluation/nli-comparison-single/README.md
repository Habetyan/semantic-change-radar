# NLI model diagnostic under single-pair inference

This run uses the current production NLI policy: each directional pair is inferred separately, with batch size 1. It repeats the fixed-classifier diagnostic on the same 35 known-development-data gold-aligned changed singleton pairs: 17 material edits and 18 rewordings. Labels remain provisional AI-reviewed labels. No fresh data, alignment decisions, threshold tuning, training, or conversion are involved. Unchanged groups, uncertain gold, additions, removals, and split/merge groups are excluded.

| Measure | Current MiniLM | DeBERTa v3 small |
|---|---:|---:|
| Material precision | 0.579 | 0.556 |
| Material recall | 0.647 | 0.588 |
| Material F1 | 0.611 | 0.571 |
| Correct material predictions | 11/17 | 10/17 |
| False material predictions | 8 | 8 |
| Correct status | 17/35 | 18/35 |
| Material edits called equivalent | 1 | 1 |
| Abstentions | 9 | 8 |
| Warm median, all 70 directional pairs | 0.957 s | 1.634 s |
| Initialization, cached assets | 0.204 s | 0.741 s |
| First inference | 1.076 s | 1.668 s |
| Quantized ONNX weight size | 82.8 MB | 172.5 MB |

Recommendation: retain MiniLM as the default. At the current inference policy, DeBERTa loses one material true positive with the same eight false positives and costs 1.71 times the warm inference latency. Its one additional correct overall status and one fewer abstention do not improve the primary material metric. Neither model exceeds the always-material baseline's F1 of 0.654 on this small selected set; this baseline necessarily flags every harmless rewording too. The results do not establish generalization or statistical significance.

The preceding batch-size-8 experiment remains intact in `../nli-comparison/`. Its candidate advantage does not reproduce under batch size 1. Its `batch-check.json` demonstrated that identical target text receives different scores when packed with other inputs under the quantized execution. Scores from those historical reports should not be combined with this current-policy run.

`stability-check.json` tests the production `Models.predict_nli` path directly: the problematic `pytest-goodpractices old[23] -> new[29]` pair and its reverse are inferred alone and inside two different surrounding pair lists. Maximum probability difference is exactly **0.0**, passing tolerance **1e-7**. This is a targeted check, not a proof covering every input, hardware platform, or runtime version. Single-pair inference removes the observed shared-batch dependence without truncating text; the specific roles of dynamic activation quantization and padding in the historical variation were not independently isolated.

Both models completed all 35 pairs without token-limit exclusions or setup failures. The experiment uses CPU ONNX Runtime, two intra-op threads, fixed guards/thresholds, and three warm timing repetitions. Timing is descriptive on one host without process isolation. Cached initialization and timing are not directly comparable to the earlier download-inclusive first run.

Model revisions and weight hashes are recorded in `summary.json`. MiniLM is pinned to `b95119ce93d3e065de6214e38cd4a97b0f2f2c6d`; DeBERTa is pinned to `fa2804872c3b4bd748f38c0185cc85775361e735`. The [official candidate model card](https://huggingface.co/cross-encoder/nli-deberta-v3-small) identifies Apache-2.0 licensing and SNLI/MultiNLI training. No production model choice changed.

Reproduce from the repository root:

```bash
.venv/bin/python -m evaluation.compare_nli --batch-size 1 --warm-runs 3 --output artifacts/local/nli-comparison-single
```

The script also accepts `--batch-size 8` for explicit historical-policy diagnostics and defaults to 1. `summary.json` preserves code/source/model hashes, runtime settings, all timings, metrics, exclusions, and failures. `predictions.jsonl` contains both passages, IDs, probabilities, guards, and classifications. `run.log` is the actual run output. Ruff passed after formatting the benchmark script.
