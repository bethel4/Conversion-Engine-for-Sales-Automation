from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from .briefs import produce_hiring_signal_brief, write_hiring_signal_brief_file


def run_hiring_signal_enrichment(
    company_name: str,
    *,
    domain: str | None = None,
    leadership_sources: list[dict[str, Any]] | None = None,
    out_dir: str | Path = "data/briefs",
    today: date | None = None,
    use_playwright: bool = False,
    jobs_html: str | None = None,
) -> dict[str, Any]:
    """
    Central merger for Act II:
    - Runs all enrichers
    - Produces one schema (`hiring_signal_brief`)
    - Writes `hiring_signal_brief_<company>_<date>.json`

    Returns: { brief, brief_path }
    """

    brief = produce_hiring_signal_brief(
        company_name,
        domain=domain,
        leadership_sources=leadership_sources,
        today=today,
        jobs_html=jobs_html,
        use_playwright=use_playwright,
    )
    path = write_hiring_signal_brief_file(brief, out_dir=out_dir)
    return {"brief": brief, "brief_path": str(path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run hiring signal enrichment pipeline (central merger)")
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument("--domain", help="Optional domain override")
    parser.add_argument("--out-dir", default="data/briefs", help="Output directory")
    parser.add_argument("--use-playwright", action="store_true", help="Use Playwright for job scraping")
    parser.add_argument("--jobs-html-file", help="Use local HTML file instead of fetching")
    parser.add_argument(
        "--leadership-sources-file",
        help="Path to JSON file containing leadership sources list: [{text,date,source}, ...]",
    )
    args = parser.parse_args(argv)

    jobs_html = None
    if args.jobs_html_file:
        jobs_html = Path(args.jobs_html_file).read_text(encoding="utf-8")

    leadership_sources = None
    if args.leadership_sources_file:
        leadership_sources = json.loads(Path(args.leadership_sources_file).read_text(encoding="utf-8"))

    result = run_hiring_signal_enrichment(
        args.company,
        domain=args.domain,
        leadership_sources=leadership_sources,
        out_dir=args.out_dir,
        use_playwright=args.use_playwright,
        jobs_html=jobs_html,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

