"""Pinned, quantized CPU inference without PyTorch or Transformers."""

from __future__ import annotations

import json
import platform
from pathlib import Path
from threading import Lock

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
NLI_MODEL = "cross-encoder/nli-MiniLM2-L6-H768"
NLI_REVISION = "b95119ce93d3e065de6214e38cd4a97b0f2f2c6d"
BATCH_SIZE = 8
CPU_THREADS = 2


def _mean_pool(hidden: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    """Ignore padding, then normalize each sentence embedding to unit length."""
    mask = attention_mask[..., None].astype(np.float32)
    pooled = (hidden * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
    return pooled / np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)


def _nli_labels(config: dict) -> list[str]:
    mapping = config["id2label"]
    labels = [mapping[str(index)].lower() for index in range(len(mapping))]
    if len(labels) != 3 or set(labels) != {"entailment", "contradiction", "neutral"}:
        raise ValueError(f"Unexpected NLI label mapping: {mapping!r}")
    return labels


def _probabilities(logits: np.ndarray, labels: list[str]) -> list[dict[str, float]]:
    scores = np.exp(logits - logits.max(axis=1, keepdims=True))
    scores /= scores.sum(axis=1, keepdims=True)
    return [dict(zip(labels, map(float, row))) for row in scores]


class _OnnxModel:
    def __init__(self, repo: str, revision: str, *, embedding: bool = False):
        self.repo = repo
        self.revision = revision
        self.filename = (
            "onnx/model_qint8_arm64.onnx"
            if platform.machine().lower() in {"arm64", "aarch64"}
            else "onnx/model_quint8_avx2.onnx"
        )

        def download(filename: str) -> str:
            return hf_hub_download(repo, filename, revision=revision)

        self.config = json.loads(Path(download("config.json")).read_text())
        tokenizer_config = json.loads(Path(download("tokenizer_config.json")).read_text())
        self.max_length = min(
            tokenizer_config["model_max_length"], self.config["max_position_embeddings"]
        )
        if embedding:
            sentence_config = json.loads(Path(download("sentence_bert_config.json")).read_text())
            self.max_length = min(self.max_length, sentence_config["max_seq_length"])
        self.tokenizer = Tokenizer.from_file(download("tokenizer.json"))
        # Configure once. Calls only encode individual inputs, with no shared mutation
        # or Rayon worker pool; padding is applied to each batch below.
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        options = ort.SessionOptions()
        options.intra_op_num_threads = CPU_THREADS
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(
            download(self.filename), options, providers=["CPUExecutionProvider"]
        )
        self.input_names = {item.name for item in self.session.get_inputs()}

    def _inputs(self, items: list[str] | list[tuple[str, str]], offset: int) -> dict:
        encoded = [
            self.tokenizer.encode(*item) if isinstance(item, tuple) else self.tokenizer.encode(item)
            for item in items
        ]
        for index, item in enumerate(encoded, start=offset + 1):
            if len(item.ids) > self.max_length:
                unit = "NLI pair" if isinstance(items[0], tuple) else "Passage"
                raise ValueError(
                    f"{unit} {index} has {len(item.ids)} tokens; the model limit is "
                    f"{self.max_length}, including special tokens. Split long passages "
                    "into shorter paragraphs."
                )
        shape = (len(items), max(len(item.ids) for item in encoded))
        input_ids = np.full(shape, self.config["pad_token_id"], dtype=np.int64)
        attention_mask = np.zeros(shape, dtype=np.int64)
        token_type_ids = np.zeros(shape, dtype=np.int64)
        for row, item in enumerate(encoded):
            length = len(item.ids)
            input_ids[row, :length] = item.ids
            attention_mask[row, :length] = item.attention_mask
            token_type_ids[row, :length] = item.type_ids
        arrays = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
        }
        return {name: arrays[name] for name in self.input_names}

    def batches(self, items: list[str] | list[tuple[str, str]], *, batch_size: int = BATCH_SIZE):
        for start in range(0, len(items), batch_size):
            inputs = self._inputs(items[start : start + batch_size], start)
            output = self.session.run(None, inputs)[0]
            yield output, inputs["attention_mask"]

    def metadata(self) -> dict:
        return {
            "repo": self.repo,
            "revision": self.revision,
            "file": self.filename,
            "max_tokens": self.max_length,
        }


class Models:
    def __init__(self):
        self.encoder = _OnnxModel(EMBEDDING_MODEL, EMBEDDING_REVISION, embedding=True)
        self.nli = _OnnxModel(NLI_MODEL, NLI_REVISION)
        self.labels = _nli_labels(self.nli.config)

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.encoder.config["hidden_size"]), dtype=np.float32)
        return np.concatenate(
            [_mean_pool(output, mask) for output, mask in self.encoder.batches(texts)]
        )

    def predict_nli(self, pairs: list[tuple[str, str]]) -> list[dict[str, float]]:
        return [
            row
            # Dynamic int8 outputs depend materially on neighboring examples
            # in the batch. Individual pairs make each verdict independent.
            for output, _ in self.nli.batches(pairs, batch_size=1)
            for row in _probabilities(output, self.labels)
        ]

    def fits_embedding(self, text: str) -> bool:
        """Budget optional group candidates without truncating source passages."""
        return len(self.encoder.tokenizer.encode(text).ids) <= self.encoder.max_length

    def fits_nli(self, left: str, right: str) -> bool:
        return len(self.nli.tokenizer.encode(left, right).ids) <= self.nli.max_length

    def metadata(self) -> dict:
        return {
            "embedding": self.encoder.metadata(),
            "nli": self.nli.metadata(),
            "runtime": "onnxruntime",
            "runtime_version": ort.__version__,
            "provider": "CPUExecutionProvider",
            "batch_size": BATCH_SIZE,
            "nli_batch_size": 1,
            "cpu_threads": CPU_THREADS,
        }


_models: Models | None = None
_models_lock = Lock()


def get_models() -> Models:
    """Initialize once, including when concurrent requests arrive on a cold start."""
    global _models
    with _models_lock:
        if _models is None:
            _models = Models()
        return _models
