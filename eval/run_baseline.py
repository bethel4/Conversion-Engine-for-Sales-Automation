#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.tau2_harness import PROVIDED_BASELINE


DEFAULT_OUTPUT_PATH = Path("eval/baseline_reference.json")


def build_baseline_payload() -> dict[str, object]:
    return {
        "message": (
            "The baseline was provided by the program to ensure consistent comparison. "
            "We do not run the baseline benchmark locally."
        ),
        "provided_baseline": dict(PROVIDED_BASELINE),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the program-provided τ² retail baseline reference")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Path to write the provided baseline reference JSON",
    )
    args = parser.parse_args(argv)

    payload = build_baseline_payload()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
