from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = REPO_ROOT / "data" / "raw" / "crunchbase" / "crunchbase-companies-information.csv"
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "briefs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run enrichment pipeline for companies in the local Crunchbase CSV.")
    parser.add_argument("--csv-path", type=Path, default=DEFAULT_CSV_PATH, help="Path to Crunchbase CSV")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Directory for generated brief files")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N companies")
    parser.add_argument("--start-at", type=int, default=0, help="Skip the first N rows before processing")
    parser.add_argument("--dry-run", action="store_true", help="Print companies without running enrichment")
    return parser.parse_args()


def iter_companies(csv_path: Path) -> list[str]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Crunchbase CSV not found: {csv_path}")

    companies: list[str] = []
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            company = (row.get("name") or "").strip()
            if company:
                companies.append(company)
    return companies


def run_company(company: str, out_dir: Path) -> int:
    command = [
        sys.executable,
        "-m",
        "agent.enrichment.pipeline",
        "--company",
        company,
        "--out-dir",
        str(out_dir),
    ]
    result = subprocess.run(command, cwd=REPO_ROOT, check=False)
    return result.returncode


def main() -> int:
    args = parse_args()
    companies = iter_companies(args.csv_path)
    selected = companies[args.start_at :]
    if args.limit is not None:
        selected = selected[: args.limit]

    if not selected:
        print("No companies selected.")
        return 0

    args.out_dir.mkdir(parents=True, exist_ok=True)

    successes = 0
    failures = 0

    for index, company in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] {company}")
        if args.dry_run:
            continue

        code = run_company(company, args.out_dir)
        if code == 0:
            successes += 1
        else:
            failures += 1
            print(f"  failed with exit code {code}")

    if args.dry_run:
        print(f"Listed {len(selected)} companies.")
        return 0

    print(f"Completed. success={successes} failure={failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
