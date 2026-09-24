"""Source-integrity checks for the blind corpus adapter, without model inference."""

import json
from pathlib import Path

import pytest

from evaluation.acquire_blind import extract_markdown
from evaluation.real_evaluate import validate_events
from radar.compare import split_passages

ROOT = Path(__file__).resolve().parents[1]


def test_visible_example_titles_and_admonition_prose_survive_code_omission():
    raw = """# Config

```python title="settings.py"
secret = 123
```

!!! tip

    Keep secrets out of logs.

<details>
<summary>Options <code>example</code></summary>
```{program-output} example --help
```
</details>
"""
    text, audit = extract_markdown(raw)
    assert split_passages(text) == [
        "# Config",
        "settings.py:",
        "Tip: Keep secrets out of logs.",
        "Options example",
    ]
    assert audit["omissions"][0]["start_line"] == 3
    assert audit["omissions"][0]["end_line"] == 5
    assert "secret = 123" not in text
    with pytest.raises(ValueError, match="Unsupported directive"):
        extract_markdown("```{unknown}\nImportant prose\n```")


def test_saved_full_pages_reproduce_and_annotations_partition_every_passage():
    manifest = json.loads((ROOT / "evaluation/blind-v3/manifest.json").read_text())
    for case in manifest["cases"]:
        passages = []
        for side in ("old", "new"):
            record = case[side]
            text, audit = extract_markdown((ROOT / record["raw_path"]).read_text())
            assert text == (ROOT / record["text_path"]).read_text()
            assert audit == json.loads((ROOT / record["audit_path"]).read_text())
            saved = json.loads((ROOT / record["passages_path"]).read_text())
            assert split_passages(text) == saved
            passages.append(saved)
        annotations = json.loads((ROOT / case["annotation_path"]).read_text())
        validate_events(*passages, annotations["events"])
