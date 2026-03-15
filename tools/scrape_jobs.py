"""
scrape_jobs.py
──────────────
Uses Playwright with saved cookies to search LinkedIn Jobs and scrape listings.

For each keyword/location combination it:
  - Navigates to the LinkedIn jobs search page
  - Scrolls to load all cards (up to max_results)
  - Clicks each card, extracts title/company/location/description/apply URL
  - Extracts any contact email found in the description text

Writes output to .tmp/raw_jobs.json.

Usage:
    python tools/scrape_jobs.py
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

load_dotenv()

COOKIES_PATH = os.getenv("LINKEDIN_COOKIES_PATH", ".tmp/linkedin_cookies.json")
KEYWORDS_RAW = os.getenv("JOB_SEARCH_KEYWORDS", "")
LOCATION = os.getenv("JOB_SEARCH_LOCATION", "Remote")
MAX_RESULTS = int(os.getenv("JOB_SEARCH_MAX_RESULTS", "30"))
OUTPUT_PATH = ".tmp/raw_jobs.json"

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("scrape_jobs")


class LinkedInSessionError(Exception):
    pass


class CaptchaError(Exception):
    pass


def load_cookies(cookies_path: str) -> list:
    path = Path(cookies_path)
    if not path.exists():
        raise LinkedInSessionError(
            f"Cookies file not found: {cookies_path}\n"
            "Run 'python tools/save_linkedin_session.py' first."
        )
    with open(path) as f:
        return json.load(f)


def check_for_wall(page: Page) -> None:
    url = page.url
    if "authwall" in url or "linkedin.com/login" in url or "checkpoint" in url:
        raise LinkedInSessionError(
            "LinkedIn redirected to login/checkpoint page — session expired.\n"
            "Re-run: python tools/save_linkedin_session.py"
        )
    if "captcha" in url.lower() or page.query_selector("[id*='captcha']"):
        raise CaptchaError(
            "CAPTCHA detected. Saved partial results. Resolve manually and retry."
        )


def scroll_job_list(page: Page, target_count: int) -> None:
    """Scroll the job list panel to load more cards."""
    for _ in range(20):
        cards = page.query_selector_all("li.jobs-search-results__list-item")
        if len(cards) >= target_count:
            break
        page.evaluate(
            """
            const list = document.querySelector('.jobs-search-results-list');
            if (list) list.scrollTop = list.scrollHeight;
            """
        )
        time.sleep(1.2)


def extract_job_detail(page: Page, job_id: str) -> dict | None:
    """Extract job details from the currently open detail panel."""
    try:
        # Wait for the job detail to load
        page.wait_for_selector(".jobs-search__job-details", timeout=8000)
    except Exception:
        log.warning("Detail panel did not load for job_id=%s", job_id)
        return None

    def safe(selector: str) -> str:
        try:
            el = page.query_selector(selector)
            return el.inner_text().strip() if el else ""
        except Exception:
            return ""

    title = safe("h1.job-details-jobs-unified-top-card__job-title") or \
            safe(".job-details-jobs-unified-top-card__job-title")
    company = safe(".job-details-jobs-unified-top-card__company-name") or \
              safe(".jobs-unified-top-card__company-name")
    location = safe(".job-details-jobs-unified-top-card__bullet") or \
               safe(".jobs-unified-top-card__bullet")
    posted = safe(".job-details-jobs-unified-top-card__posted-date") or \
             safe(".jobs-unified-top-card__posted-date")

    description = ""
    try:
        desc_el = page.query_selector(".jobs-description__content") or \
                  page.query_selector("#job-details")
        if desc_el:
            description = desc_el.inner_text().strip()
    except Exception:
        pass

    contact_email = None
    if description:
        email_match = EMAIL_RE.search(description)
        if email_match:
            contact_email = email_match.group()

    apply_url = f"https://www.linkedin.com/jobs/view/{job_id}"

    return {
        "job_id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "posted_date": posted,
        "description": description[:3000],
        "apply_url": apply_url,
        "contact_email": contact_email,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def scrape_keyword(
    page: Page,
    keyword: str,
    location: str,
    max_per_keyword: int,
    seen_ids: set,
) -> list[dict]:
    results = []
    url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={quote_plus(keyword)}&location={quote_plus(location)}"
        f"&f_TPR=r2592000"  # posted in last 30 days
    )
    log.info("Searching: '%s' in '%s'", keyword, location)
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)
    check_for_wall(page)

    scroll_job_list(page, max_per_keyword)
    cards = page.query_selector_all("li.jobs-search-results__list-item")
    log.info("Found %d job cards for '%s'", len(cards), keyword)

    for card in cards[:max_per_keyword]:
        try:
            job_id = card.get_attribute("data-occludable-job-id") or \
                     card.get_attribute("data-job-id")
            if not job_id:
                # Try extracting from link href
                link = card.query_selector("a[href*='/jobs/view/']")
                if link:
                    href = link.get_attribute("href") or ""
                    match = re.search(r"/jobs/view/(\d+)", href)
                    job_id = match.group(1) if match else None

            if not job_id or job_id in seen_ids:
                continue

            seen_ids.add(job_id)
            card.click()
            time.sleep(1.0 + (hash(job_id) % 5) * 0.2)  # randomised 1.0-2.0s

            detail = extract_job_detail(page, job_id)
            if detail and detail.get("title"):
                results.append(detail)
                log.info("  [%d] %s @ %s", len(results), detail["title"], detail["company"])

        except Exception as e:
            log.warning("Error processing card: %s", e)
            continue

    return results


def scrape_jobs(
    cookies_path: str = COOKIES_PATH,
    keywords: list | None = None,
    location: str = LOCATION,
    max_results: int = MAX_RESULTS,
    output_path: str = OUTPUT_PATH,
) -> list[dict]:
    if keywords is None:
        keywords = [k.strip() for k in KEYWORDS_RAW.split(",") if k.strip()]
    if not keywords:
        raise ValueError(
            "JOB_SEARCH_KEYWORDS is not set in .env\n"
            "Set it to comma-separated keywords, e.g.:\n"
            "  JOB_SEARCH_KEYWORDS=Python Engineer,Backend Developer"
        )

    cookies = load_cookies(cookies_path)
    per_keyword = max(1, max_results // len(keywords))

    all_jobs: list[dict] = []
    seen_ids: set = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=500)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        context.add_cookies(cookies)
        page = context.new_page()

        try:
            for keyword in keywords:
                jobs = scrape_keyword(page, keyword, location, per_keyword, seen_ids)
                all_jobs.extend(jobs)
        except (LinkedInSessionError, CaptchaError) as e:
            log.error(str(e))
            # Save partial results before raising
            if all_jobs:
                _save(all_jobs, output_path)
                log.info("Partial results saved (%d jobs)", len(all_jobs))
            browser.close()
            raise
        finally:
            browser.close()

    if not all_jobs:
        log.warning("No jobs scraped. Check keywords, location, and session cookies.")
    else:
        _save(all_jobs, output_path)
        log.info("Saved %d jobs to %s", len(all_jobs), output_path)

    return all_jobs


def _save(jobs: list[dict], path: str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    scrape_jobs()
