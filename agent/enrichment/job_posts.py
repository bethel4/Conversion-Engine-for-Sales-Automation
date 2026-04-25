from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
from typing import Any, Iterable

import requests
try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore[assignment]
import html as _html

from .cache import get_cache, list_cache, set_cache
from .crunchbase import normalize_company_name


ENGINEERING_KEYWORDS = (
    "engineer",
    "engineering",
    "developer",
    "development",
    "devops",
    "sre",
    "site reliability",
    "platform",
    "backend",
    "front end",
    "frontend",
    "full stack",
    "full-stack",
    "software",
    "mobile",
    "ios",
    "android",
    "data engineer",
    "data platform",
    "security",
    "infrastructure",
    "infra",
    "cloud",
    "qa",
    "test automation",
)

AI_ML_KEYWORDS = (
    "machine learning",
    "ml ",
    " ml",
    "ai ",
    " ai",
    "artificial intelligence",
    "data scientist",
    "applied scientist",
    "research scientist",
    "deep learning",
    "nlp",
    "computer vision",
    "llm",
    "genai",
    "generative",
    "mlops",
)

PUBLIC_JOB_SOURCES = (
    "company_careers_page",
    "builtin_public_company_jobs",
    "wellfound_public_company_jobs",
    "linkedin_public_company_jobs",
)


def scrape_job_posts(
    domain: str,
    *,
    company_name: str | None = None,
    days_back: int = 60,
    today: date | None = None,
    use_playwright: bool = False,
    html: str | None = None,
) -> dict[str, Any]:
    """
    Returns:
      {
        total_open_roles,
        engineering_roles,
        ai_ml_roles,
        velocity_60d,
        open_roles_60_days_ago,
        signal_strength,
        source_url,
        source_urls,
        checked_at,
        robots_policy
      }

    Public-page only constraints:
    - Only first-party careers pages plus public BuiltIn / Wellfound / LinkedIn company job pages.
    - No login-required flows, private APIs, or authenticated scraping.
    - robots.txt is checked before fetching each page and non-allowed pages are skipped.

    `velocity_60d` is computed as the engineering-role count delta versus the nearest
    cached snapshot from ~60 days ago.
    """

    if today is None:
        today = date.today()

    key = normalize_company_name(company_name or domain)
    if not key:
        return _empty()

    cached = get_cache("job_posts_latest", key, max_age_seconds=24 * 3600)
    if isinstance(cached, dict):
        return cached  # type: ignore[return-value]

    if html is None:
        urls = guess_public_job_source_urls(domain, company_name=company_name)
        html, used_url, used_meta = _fetch_first_html(urls, use_playwright=use_playwright)
    else:
        urls = []
        used_url = None
        used_meta = {"source": "provided_html", "robots_allowed": True, "robots_txt_url": None}

    titles = extract_job_titles(html or "")
    counts = classify_job_titles(titles)

    velocity, previous_count = compute_velocity_60d(
        key,
        current_engineering_roles=counts["engineering_roles"],
        today=today,
        days_back=days_back,
    )
    result = {
        **counts,
        "velocity_60d": velocity,
        "open_roles_60_days_ago": previous_count,
        "signal_strength": _signal_strength(counts["engineering_roles"]),
        "source_url": used_url,
        "source_urls": [item["url"] for item in urls],
        "source_type": used_meta.get("source"),
        "checked_at": today.isoformat(),
        "robots_policy": {
            "checked": True,
            "allowed": bool(used_meta.get("robots_allowed", True)),
            "robots_txt_url": used_meta.get("robots_txt_url"),
            "public_page_only": True,
        },
    }

    # Persist snapshot for future velocity calculations.
    snapshot_key = f"{key}:{today.isoformat()}"
    set_cache("job_posts_snapshot", snapshot_key, result)
    set_cache("job_posts_latest", key, result)
    return result


def guess_public_job_source_urls(domain: str, *, company_name: str | None = None) -> list[dict[str, str]]:
    d = domain.strip().rstrip("/")
    if not d:
        return []
    if not re.match(r"^https?://", d):
        base = f"https://{d}"
    else:
        base = d
        d = re.sub(r"^https?://", "", d).split("/", 1)[0]

    slug = normalize_company_name(company_name or d).replace(" ", "-")
    return [
        {"source": "company_careers_page", "url": f"{base}/careers"},
        {"source": "company_careers_page", "url": f"{base}/jobs"},
        {"source": "company_careers_page", "url": f"{base}/careers/jobs"},
        {"source": "company_careers_page", "url": f"https://jobs.{d}"},
        {"source": "company_careers_page", "url": f"https://careers.{d}"},
        {"source": "builtin_public_company_jobs", "url": f"https://www.builtin.com/company/{slug}/jobs"},
        {"source": "wellfound_public_company_jobs", "url": f"https://wellfound.com/company/{slug}/jobs"},
        {"source": "linkedin_public_company_jobs", "url": f"https://www.linkedin.com/company/{slug}/jobs/"},
    ]


def extract_job_titles(html: str) -> list[str]:
    if BeautifulSoup is None:
        return _extract_job_titles_fallback(html or "")

    soup = BeautifulSoup(html or "", "lxml")

    candidates: list[str] = []

    # Common ATS markers (Greenhouse, Lever, Workable, etc.)
    selectors = [
        "[data-automation='jobTitle']",
        "[data-qa='posting-name']",
        ".posting-title",
        ".opening a",
        ".openings a",
        "a[href*='jobs']",
        "a[href*='careers']",
        "a[href*='lever.co']",
        "a[href*='greenhouse.io']",
        "h2",
        "h3",
        "h4",
    ]
    for sel in selectors:
        for el in soup.select(sel):
            text = _clean_title(el.get_text(" ", strip=True))
            if _looks_like_title(text):
                candidates.append(text)

    # De-dupe while preserving order.
    seen: set[str] = set()
    titles: list[str] = []
    for t in candidates:
        k = t.casefold()
        if k in seen:
            continue
        seen.add(k)
        titles.append(t)
    return titles


def _extract_job_titles_fallback(html: str) -> list[str]:
    """
    Minimal dependency-free fallback (regex-based) for environments without bs4/lxml.
    """

    candidates: list[str] = []
    for tag in ("h2", "h3", "h4"):
        for inner in re.findall(rf"<{tag}[^>]*>(.*?)</{tag}>", html, flags=re.I | re.S):
            text = _clean_title(_strip_tags(inner))
            if _looks_like_title(text):
                candidates.append(text)

    for href, inner in re.findall(
        r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html, flags=re.I | re.S
    ):
        href_cf = href.casefold()
        if not any(k in href_cf for k in ("job", "career", "lever.co", "greenhouse.io")):
            continue
        text = _clean_title(_strip_tags(inner))
        if _looks_like_title(text):
            candidates.append(text)

    seen: set[str] = set()
    out: list[str] = []
    for t in candidates:
        k = t.casefold()
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


def _strip_tags(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text or "")
    cleaned = _html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def classify_job_titles(titles: Iterable[str]) -> dict[str, int]:
    total = 0
    engineering = 0
    ai_ml = 0
    for title in titles:
        title = title.strip()
        if not title:
            continue
        total += 1
        if is_engineering_role(title):
            engineering += 1
        if is_ai_ml_role(title):
            ai_ml += 1
    return {
        "total_open_roles": total,
        "engineering_roles": engineering,
        "ai_ml_roles": ai_ml,
    }


def compute_velocity_60d(
    company_key: str,
    *,
    current_engineering_roles: int,
    today: date,
    days_back: int = 60,
) -> tuple[int | None, int | None]:
    target = today - timedelta(days=days_back)
    rows = list_cache("job_posts_snapshot", f"{company_key}:")
    best_count: int | None = None
    best_delta: int | None = None
    for row in rows:
        key = row.get("key")
        if not isinstance(key, str) or ":" not in key:
            continue
        snapshot_date_str = key.rsplit(":", 1)[-1]
        try:
            snap_date = date.fromisoformat(snapshot_date_str[:10])
        except Exception:
            continue
        delta = abs((snap_date - target).days)
        value = row.get("value")
        if not isinstance(value, dict):
            continue
        prev_eng = value.get("engineering_roles")
        if not isinstance(prev_eng, int):
            continue
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_count = prev_eng

    if best_count is None or best_count < 1:
        return None, None
    return current_engineering_roles - best_count, best_count


def is_engineering_role(title: str) -> bool:
    t = title.casefold()
    return any(k in t for k in ENGINEERING_KEYWORDS)


def is_ai_ml_role(title: str) -> bool:
    t = title.casefold()
    return any(k in t for k in AI_ML_KEYWORDS)


def _signal_strength(engineering_roles: int) -> str:
    if engineering_roles >= 10:
        return "strong"
    if engineering_roles >= 5:
        return "medium"
    if engineering_roles >= 2:
        return "weak"
    return "none"


def _looks_like_title(text: str) -> bool:
    if not text:
        return False
    if len(text) < 4 or len(text) > 120:
        return False
    if not re.search(r"[A-Za-z]", text):
        return False
    # Avoid nav/footer noise.
    if text.casefold() in {"careers", "jobs", "apply", "open roles"}:
        return False
    return True


def _clean_title(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def _fetch_first_html(urls: list[dict[str, str]], *, use_playwright: bool) -> tuple[str, str | None, dict[str, Any]]:
    last_err: Exception | None = None
    for entry in urls:
        url = entry["url"]
        try:
            robots = check_robots_txt(url)
            if not robots["allowed"]:
                last_err = RuntimeError(f"robots.txt disallows fetch for {url}")
                continue
            return fetch_html(url, use_playwright=use_playwright), url, {
                "source": entry["source"],
                "robots_allowed": True,
                "robots_txt_url": robots["robots_txt_url"],
            }
        except Exception as exc:
            last_err = exc
            continue
    if last_err is not None:
        raise last_err
    return "", None, {"source": None, "robots_allowed": False, "robots_txt_url": None}


def check_robots_txt(url: str, *, timeout_seconds: int = 10) -> dict[str, Any]:
    parsed = urlparse(url)
    robots_txt_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    path = parsed.path or "/"
    try:
        response = requests.get(
            robots_txt_url,
            timeout=timeout_seconds,
            headers={"User-Agent": "TenaciousEnrichmentBot/1.0"},
        )
    except requests.RequestException:
        return {"allowed": True, "robots_txt_url": robots_txt_url}
    if response.status_code >= 400:
        return {"allowed": True, "robots_txt_url": robots_txt_url}

    allow = True
    applies = False
    for raw_line in response.text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key_cf = key.strip().casefold()
        value = value.strip()
        if key_cf == "user-agent":
            applies = value in {"*", "TenaciousEnrichmentBot", "TenaciousEnrichmentBot/1.0"}
        elif applies and key_cf == "disallow" and value:
            disallowed_path = urljoin(f"{parsed.scheme}://{parsed.netloc}", value)
            disallowed_only_path = urlparse(disallowed_path).path or value
            if path.startswith(disallowed_only_path):
                allow = False
        elif applies and key_cf == "allow" and value:
            allowed_path = urljoin(f"{parsed.scheme}://{parsed.netloc}", value)
            allowed_only_path = urlparse(allowed_path).path or value
            if path.startswith(allowed_only_path):
                allow = True
    return {"allowed": allow, "robots_txt_url": robots_txt_url}


def fetch_html(url: str, *, use_playwright: bool = False, timeout_seconds: int = 15) -> str:
    if use_playwright:
        html = _fetch_with_playwright(url, timeout_seconds=timeout_seconds)
        if html is None:
            raise RuntimeError(
                "Playwright requested but not available. Install dependencies and run "
                "`python -m playwright install chromium`."
            )
        return html

    resp = requests.get(
        url,
        timeout=timeout_seconds,
        headers={"User-Agent": "TenaciousEnrichmentBot/1.0"},
    )
    resp.raise_for_status()
    return resp.text


def _fetch_with_playwright(url: str, *, timeout_seconds: int) -> str | None:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        return None

    timeout_ms = int(timeout_seconds * 1000)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            return page.content()
        finally:
            browser.close()


def _empty() -> dict[str, Any]:
    return {
        "total_open_roles": 0,
        "engineering_roles": 0,
        "ai_ml_roles": 0,
        "velocity_60d": None,
        "open_roles_60_days_ago": None,
        "signal_strength": "none",
        "source_url": None,
        "source_urls": [],
        "source_type": None,
        "checked_at": None,
        "robots_policy": {
            "checked": True,
            "allowed": True,
            "robots_txt_url": None,
            "public_page_only": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Job-post scraping signal")
    parser.add_argument("--domain", required=True, help="Company domain (e.g. stripe.com)")
    parser.add_argument("--company", help="Optional company name (for caching key)")
    parser.add_argument("--use-playwright", action="store_true", help="Use Playwright if available")
    parser.add_argument("--html-file", help="Parse a local saved HTML file instead of fetching")
    args = parser.parse_args(argv)

    html = None
    if args.html_file:
        html = Path(args.html_file).read_text(encoding="utf-8")

    result = scrape_job_posts(
        args.domain,
        company_name=args.company,
        use_playwright=args.use_playwright,
        html=html,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
