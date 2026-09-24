# NLI model diagnostic

This is a known-development-data diagnostic, not a held-out result or an alignment benchmark. The 35 eligible gold-aligned changed singleton groups contain 17 material edits and 18 rewordings. Labels are provisional AI-reviewed labels. Unchanged groups, uncertain labels, additions, removals, and split/merge groups were excluded before inference. No fresh-v2 data was accessed.

Both models used the existing `_classify` function, its fixed guards and thresholds, identical passage pairs in both directions, CPU ONNX Runtime, batch size 8, and two intra-op threads. No tuning, truncation, training, conversion, or new dependency installation was performed. All 35 pairs fit both models' 512-token limits and completed successfully.

| Measure | Current MiniLM | DeBERTa v3 small |
|---|---:|---:|
| Material precision | 0.688 | 0.706 |
| Material recall | 0.647 | 0.706 |
| Material F1 | 0.667 | 0.706 |
| Correct status | 17/35 | 22/35 |
| Material edits called equivalent | 1 | 1 |
| Abstentions | 12 | 7 |
| Warm median, all 70 directional pairs | 1.584 s | 2.992 s |
| Initialization, including cache misses | 0.219 s | 11.705 s |
| First inference | 1.574 s | 3.077 s |
| Initialization plus first inference | 1.793 s | 14.782 s |
| Quantized ONNX weight size | 82.8 MB | 172.5 MB |

The always-material baseline has precision 0.486, recall 1.000, and F1 0.654. DeBERTa's material gain is one extra true positive with the same five false positives; lower abstention also improves four other correct decisions. It introduces one false material call from a former abstention on `pytest-goodpractices old[26] -> new[47]`, where “as a workaround” is inserted. The indices are zero-based.

Both models miss the same material deletion in `flask-design old[17] -> new[17]`: the newer paragraph drops the claim that Jinja2 “uses Unicode for all operations.” DeBERTa therefore does not resolve the specific long-paragraph omission failure motivating localized verification.

Recommendation: retain MiniLM as the production default. DeBERTa is a viable optional experiment, but this small, previously inspected development set shows only a modest material gain at 1.89 times the warm latency and 2.08 times the weight storage. These observations are descriptive, not evidence of a statistically reliable or held-out improvement. Timing uses three warm repetitions on one host without process isolation; initialization is not a fair cold-loading comparison because cache states differ. CPU quantization and fixed, uncalibrated thresholds also limit interpretation.

Candidate provenance: the [official model card](https://huggingface.co/cross-encoder/nli-deberta-v3-small) declares Apache-2.0 licensing and SNLI/MultiNLI training. The Hugging Face API resolved revision `fa2804872c3b4bd748f38c0185cc85775361e735`; the selected `onnx/model_quint8_avx2.onnx` is 172,503,005 bytes. The pinned configuration maps labels to contradiction, entailment, neutral and sets 512 maximum positions. Only configuration, tokenizer assets, and the selected quantized ONNX weight were requested. The production model and third-party notices remain unchanged.

Reproduce from the repository root:

```bash
.venv/bin/python -m evaluation.compare_nli --output artifacts/local/nli-comparison --warm-runs 3
```

`summary.json` records source hashes, classifier/code hashes, pinned revisions, model artifact sizes and SHA-256 hashes, runtime parameters, all timing repetitions, aggregate confusion matrices, and exclusions/failures. `predictions.jsonl` records model probabilities, decisions, guards, case IDs, passage indices, and both source passages. `run.log` is the actual run output. A hand-computed metric sanity check and Ruff passed.

## Batch-composition sensitivity check

A targeted repeat explains why this oracle benchmark records one MiniLM material-as-equivalent miss while the historical full-document evaluation records two. The second historical miss, `pytest-goodpractices old[23] -> new[29]`, uses exactly the same source strings in both runs. It changes the condition for running tests from the absence of `setup.py` to the absence of an editable installation and `src` layout.

Using the archived v1 model loader, classifier, and document comparator reproduces the historical probabilities exactly to recorded precision:

| Packing of identical target pair | Old entails new | New entails old | Decision |
|---|---:|---:|---|
| Original document batch | .873827 | .879523 | Reworded |
| Both directions together, alone | .910748 | .498565 | Needs review |
| Each direction alone | .843045 | .541310 | Needs review |
| 35-pair oracle benchmark, interleaved directions | .789453 | .480433 | Needs review |

The original target batches have token lengths `[98, 54, 74, 27, 63, 33, 19, 123]`; the oracle target batch has `[33, 33, 19, 19, 123, 123, 192, 192]`. This establishes sensitivity to batch composition under the existing quantized ONNX execution. The experiment does not isolate changed padding from shared dynamic activation quantization scales, so the precise numerical mechanism remains unconfirmed.

Consequently, the oracle table describes this exact packing and cannot be substituted for full-pipeline predictions or interpreted as a reduction from two historical misses to one. Both candidate models saw the same example ordering and batch size, but the comparison is conditional on that execution layout. Fixed seeds alone do not eliminate this sensitivity. No runtime or production-default changes were made. `batch-check.json` preserves the input identity check, archive hash, model/runtime identity, directional scores, classifications, and batch lengths for all four executions.
