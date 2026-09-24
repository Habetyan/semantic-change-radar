"""Offline checks; opt into real inference with RUN_MODEL_TESTS=1 pytest -m model -s."""

import os
from time import perf_counter
from types import SimpleNamespace

import numpy as np
import pytest
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace

from radar.models import _mean_pool, _nli_labels, _OnnxModel, _probabilities, get_models


def test_pooling_ignores_padding_and_normalizes_each_sentence():
    hidden = np.array([[[3, 0], [0, 4], [999, 999]], [[0, 2], [9, 9], [9, 9]]])
    mask = np.array([[1, 1, 0], [1, 0, 0]])
    np.testing.assert_allclose(_mean_pool(hidden, mask), [[0.6, 0.8], [0, 1]])


def test_nli_probabilities_follow_config_not_assumed_label_order():
    labels = _nli_labels({"id2label": {"0": "neutral", "1": "contradiction", "2": "entailment"}})
    scores = _probabilities(np.array([[1000.0, 1001.0, 1002.0]]), labels)[0]
    assert max(scores, key=scores.get) == "entailment"
    assert scores["contradiction"] > scores["neutral"]
    assert sum(scores.values()) == pytest.approx(1)
    with pytest.raises(ValueError, match="Unexpected NLI label"):
        _nli_labels({"id2label": {"0": "LABEL_0", "1": "LABEL_1", "2": "LABEL_2"}})


def _tiny_model() -> _OnnxModel:
    model = object.__new__(_OnnxModel)
    model.tokenizer = Tokenizer(WordLevel({"[UNK]": 0, "a": 1, "b": 2}, unk_token="[UNK]"))
    model.tokenizer.pre_tokenizer = Whitespace()
    model.config = {"pad_token_id": 0}
    model.max_length = 4
    model.input_names = {"input_ids", "attention_mask", "token_type_ids"}
    return model


def test_inputs_reject_overlength_without_truncation_and_pad_with_attention_mask():
    model = _tiny_model()
    inputs = model._inputs(["a b", "a"], offset=0)
    assert inputs["input_ids"].tolist() == [[1, 2], [1, 0]]
    assert inputs["attention_mask"].tolist() == [[1, 1], [1, 0]]
    assert inputs["input_ids"].dtype == np.int64
    with pytest.raises(ValueError, match=r"Passage 10 has 5 tokens.*limit is 4"):
        model._inputs(["a", "a a a a a"], offset=8)
    with pytest.raises(ValueError, match=r"NLI pair 1 has 5 tokens.*limit is 4"):
        model._inputs([("a a a", "b b")], offset=0)


def test_inference_batches_are_bounded_and_keep_input_order():
    model = _tiny_model()
    batch_sizes = []

    def run(_output_names, inputs):
        batch_sizes.append(len(inputs["input_ids"]))
        return [inputs["input_ids"]]

    model.session = SimpleNamespace(run=run)
    outputs = list(model.batches(["a"] * 8 + ["b"]))
    assert batch_sizes == [8, 1]
    assert outputs[-1][0].tolist() == [[2]]


@pytest.mark.model
@pytest.mark.skipif(
    os.getenv("RUN_MODEL_TESTS") != "1", reason="Set RUN_MODEL_TESTS=1 to load models"
)
def test_real_models_retrieve_a_paraphrase_and_predict_all_nli_labels():
    start = perf_counter()
    models = get_models()
    load_seconds = perf_counter() - start
    assert get_models() is models
    start = perf_counter()
    vectors = models.encode(
        [
            "You can return the product within thirty days.",
            "Products may be returned for a refund within 30 days.",
            "The server stores encrypted passwords.",
        ]
    )
    embedding_seconds = perf_counter() - start
    assert vectors.shape == (3, 384)
    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-6)
    assert vectors[0] @ vectors[1] > vectors[0] @ vectors[2] + 0.2
    start = perf_counter()
    scores = models.predict_nli(
        [
            ("A dog is running in the park.", "An animal is outdoors."),
            ("A dog is running in the park.", "There is no dog in the park."),
            ("A dog is running in the park.", "The dog belongs to Alice."),
        ]
    )
    nli_seconds = perf_counter() - start
    assert [max(row, key=row.get) for row in scores] == ["entailment", "contradiction", "neutral"]
    pair = (
        "If the account is inactive, records can be deleted.",
        "If the account is active, records can be deleted.",
    )
    alone = models.predict_nli([pair])[0]
    surrounded = models.predict_nli(
        [
            ("A short unrelated sentence.", "Something else."),
            pair,
            ("The server processes requests. " * 20, "The server exists."),
        ]
    )[1]
    assert alone == surrounded
    assert models.encode([]).shape == (0, 384)
    assert models.predict_nli([]) == []
    with pytest.raises(ValueError, match="model limit is 256"):
        models.encode(["a " * 300])
    with pytest.raises(ValueError, match="model limit is 512"):
        models.predict_nli([("a " * 300, "b " * 300)])
    print(
        f"load={load_seconds:.3f}s, three embeddings={embedding_seconds:.3f}s, "
        f"three NLI pairs={nli_seconds:.3f}s"
    )
