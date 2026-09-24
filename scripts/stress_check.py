"""Reproduce the 80-passage performance sanity check; this is not an accuracy benchmark."""

import json
import time
from collections import Counter

from radar.compare import compare_documents


def main() -> None:
    old = "\n\n".join(f"Service {i} keeps audit logs for 30 days." for i in range(80))
    new = "\n\n".join(f"Service {i} keeps audit logs for 60 days." for i in range(79, -1, -1))
    start = time.perf_counter()
    report = compare_documents(old, new)
    correct = sum(
        change["old_index"] == 79 - change["new_index"]
        for change in report["changes"]
        if change["old_index"] is not None and change["new_index"] is not None
    )
    summary = {
        "scenario": "80 passages, changed retention limits, reversed ordering",
        "elapsed_seconds": round(time.perf_counter() - start, 3),
        "statuses": dict(Counter(change["status"] for change in report["changes"])),
        "aligned_correctly": correct,
        "models": report["models"],
    }
    print(json.dumps(summary, indent=2))
    assert correct == 80 and summary["statuses"] == {"modified": 80}, summary


if __name__ == "__main__":
    main()
