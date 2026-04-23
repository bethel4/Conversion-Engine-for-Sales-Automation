#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _first_text(page: Any, selectors: list[str]) -> Optional[str]:
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.count() == 0:
                continue
            txt = el.inner_text(timeout=1000).strip()
            if txt:
                return txt
        except Exception:
            continue
    return None


def fetch_job_listing(url: str, *, headless: bool, timeout_ms: int) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Playwright is not installed. Install with `pip install playwright` and run `playwright install`."
        ) from exc

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

            title = _first_text(
                page,
                selectors=[
                    "h1",
                    "[data-testid*=title]",
                    "[class*=title] h1",
                    "meta[property='og:title'] >> xpath=..",
                ],
            )
            company = _first_text(
                page,
                selectors=[
                    "[data-testid*=company]",
                    "[class*=company]",
                    "a[href*='company']",
                ],
            )
            location = _first_text(
                page,
                selectors=[
                    "[data-testid*=location]",
                    "[class*=location]",
                    "text=/remote|hybrid|onsite|on-site/i",
                ],
            )

            # Best-effort: grab a big text block as "description".
            description = _first_text(
                page,
                selectors=[
                    "[data-testid*=description]",
                    "article",
                    "main",
                ],
            )

            return {
                "source_url": url,
                "fetched_at": _utc_now_iso(),
                "title": title,
                "company": company,
                "location": location,
                "description": description,
            }
        finally:
            browser.close()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch a single job listing page and output JSON (Playwright).")
    parser.add_argument("--url", required=True, help="Job listing URL to fetch.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output file path.")
    parser.add_argument("--timeout-ms", type=int, default=30000, help="Navigation timeout in ms.")
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run browser headless (default: true).",
    )
    args = parser.parse_args(argv)

    try:
        payload = fetch_job_listing(args.url, headless=args.headless, timeout_ms=args.timeout_ms)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.output is None:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

