# Third-party components

This project uses pretrained models as downloaded dependencies. Weights are not
committed to this repository, and this project does not claim to have trained them.

| Model | Revision | License in model card |
|---|---|---|
| [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/1110a243fdf4706b3f48f1d95db1a4f5529b4d41) | `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` | Apache-2.0 |
| [cross-encoder/nli-MiniLM2-L6-H768](https://huggingface.co/cross-encoder/nli-MiniLM2-L6-H768/tree/b95119ce93d3e065de6214e38cd4a97b0f2f2c6d) | `b95119ce93d3e065de6214e38cd4a97b0f2f2c6d` | Apache-2.0 |
| [cross-encoder/nli-deberta-v3-small](https://huggingface.co/cross-encoder/nli-deberta-v3-small/tree/fa2804872c3b4bd748f38c0185cc85775361e735), experiment only | `fa2804872c3b4bd748f38c0185cc85775361e735` | Apache-2.0 |

Runtime libraries include Gradio, NumPy, SciPy, ONNX Runtime, Hugging Face Hub, and
Hugging Face Tokenizers. Their licenses and upstream attribution remain applicable.
The complete tested package versions are recorded in `requirements.lock`.

The original `evaluation/dev.jsonl`, `evaluation/test.jsonl` and the first five
entries of `examples.json` are AI-authored synthetic text. The three later demo
examples reproduce extracted HTTPX, pip and MkDocs revision pairs from fresh-v2;
the source licenses below apply. Labels are not human validated.

## Real revision corpus

`evaluation/real/documents/` includes complete upstream RST snapshots and derived
prose from Flask, pytest and Requests. The snapshots retain upstream licensing;
the repository's MIT license does not replace those licenses. The extracted
`.txt` and `.passages.json` files are modified versions made by removing code and
some RST markup; each `.extraction.json` records source-line omissions.

| Upstream | License | Retained notices |
|---|---|---|
| Pallets Flask | BSD-3-Clause | [old](evaluation/real/licenses/flask-old-LICENSE.rst), [new](evaluation/real/licenses/flask-new-LICENSE.txt) |
| pytest | MIT | [old](evaluation/real/licenses/pytest-old-LICENSE), [new](evaluation/real/licenses/pytest-new-LICENSE) |
| Requests | Apache-2.0 | [old license](evaluation/real/licenses/requests-old-LICENSE), [new license](evaluation/real/licenses/requests-new-LICENSE), [old NOTICE](evaluation/real/licenses/requests-old-NOTICE), [new NOTICE](evaluation/real/licenses/requests-new-NOTICE) |

Exact repository paths, commit IDs, source URLs and checksums are recorded in the
[corpus manifest](evaluation/real/manifest.json). Corpus correspondence and meaning
annotations were authored and reviewed by AI agents, not validated by humans.

## Fresh revision corpus

`evaluation/fresh-v2/documents/` retains upstream Markdown snapshots and derived
prose. Source licenses continue to apply. Extraction removes fenced examples,
normalizes selected markup, and retains source-line omission audits. The
[manifest](evaluation/fresh-v2/manifest.json) pins exact commits and checksums;
both historical licenses are retained for every pair.

| Upstream | License | Retained notices |
|---|---|---|
| HTTPX | BSD-3-Clause | [old](evaluation/fresh-v2/licenses/httpx-compatibility-old-LICENSE.md), [new](evaluation/fresh-v2/licenses/httpx-compatibility-new-LICENSE.md) |
| pip | MIT | [old](evaluation/fresh-v2/licenses/pip-caching-old-LICENSE.txt), [new](evaluation/fresh-v2/licenses/pip-caching-new-LICENSE.txt) |
| MkDocs | BSD-2-Clause | [old](evaluation/fresh-v2/licenses/mkdocs-deployment-old-LICENSE), [new](evaluation/fresh-v2/licenses/mkdocs-deployment-new-LICENSE) |

Fresh annotations were independently AI-reviewed before inference and remain
pending human validation. Model weights are downloaded into the local cache,
including the experimental candidate; no weights are redistributed here.

## Blind v3 revision corpus

`evaluation/blind-v3/documents/` retains complete historical Markdown snapshots
and derived prose from Starlette, Black and uv. Upstream licenses apply to these
copies and derived files; this repository's MIT license does not replace them.
The [manifest](evaluation/blind-v3/manifest.json) records pinned commits, source
URLs, checksums and every retained license copy. Both source revisions' licenses
are stored per case, including Black cases with different newer revisions.
Extraction omits code and selected markup while retaining prose and visible
example titles; source-line audits accompany each version.

| Upstream | License | Retained notices |
| --- | --- | --- |
| Encode Starlette | BSD-3-Clause | [License copies](evaluation/blind-v3/licenses/) named `starlette-*-LICENSE.md` |
| Python Software Foundation Black | MIT | [License copies](evaluation/blind-v3/licenses/) named `black-*-LICENSE` |
| Astral uv | MIT OR Apache-2.0 | [old MIT](evaluation/blind-v3/licenses/uv-cache-old-LICENSE-MIT), [new MIT](evaluation/blind-v3/licenses/uv-cache-new-LICENSE-MIT), [old Apache](evaluation/blind-v3/licenses/uv-cache-old-LICENSE-APACHE), [new Apache](evaluation/blind-v3/licenses/uv-cache-new-LICENSE-APACHE) |

The pinned repository-root [license audit](evaluation/blind-v3/license-audit.json)
found no separate root NOTICE files. Annotation authorship and review status are
recorded separately from source licensing; no human validation is claimed.

## Local generative-model experiment

The development-only experiment used a previously cached Ollama
`qwen2.5:7b-instruct` quantized model, digest
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`.
The upstream model is [Qwen/Qwen2.5-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct),
licensed under Apache-2.0. The upstream license is retained at
[model-license.txt](artifacts/evaluation/v3-llm-qwen/model-license.txt), with local
runtime/model metadata in the [run configuration](artifacts/evaluation/v3-llm-qwen/run-config.json).
The Ollama digest identifies the tested local artifact; it is not a Hugging Face
revision ID. Model weights are not committed or redistributed, and the experiment
is not a production backend. This project did not train or fine-tune this model.
