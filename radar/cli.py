"""Command-line entry point, sharing exactly the UI comparison pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from radar.compare import MAX_CHARACTERS, compare_documents


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare meaning across two text document versions."
    )
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--backend", choices=["semantic", "lexical"], default="semantic")
    parser.add_argument(
        "--profile", choices=["baseline", "context", "groups", "verified"], default="verified"
    )
    parser.add_argument(
        "--output", type=Path, help="Write the JSON report here; default is stdout."
    )
    args = parser.parse_args()
    try:
        for path in [args.before, args.after]:
            if path.stat().st_size > MAX_CHARACTERS * 4:
                raise ValueError(f"{path} is too large; use short UTF-8 text documents.")
        result = compare_documents(
            args.before.read_text(encoding="utf-8"),
            args.after.read_text(encoding="utf-8"),
            backend=args.backend,
            profile=args.profile,
        )
        output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Comparison failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
