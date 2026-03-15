"""
scrape_linkedin_profile.py
──────────────────────────
Loads the user's LinkedIn profile page using saved cookies (no password needed),
then scrapes: name, headline, location, about, experience, education, skills,
certifications, and languages.

Writes output to .tmp/linkedin_profile.json.

Usage:
    python tools/scrape_linkedin_profile.py
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

load_dotenv()

COOKIES_PATH = os.getenv("LINKEDIN_COOKIES_PATH", ".tmp/linkedin_cookies.json")
PROFILE_URL = os.getenv("LINKEDIN_PROFILE_URL", "")
OUTPUT_PATH = ".tmp/linkedin_profile.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("scrape_linkedin_profile")


class LinkedInSessionError(Exception):
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


def scroll_to_bottom(page: Page, pause: float = 1.5) -> None:
    """Scroll page to load lazy-loaded sections."""
    prev_height = 0
    for _ in range(10):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(pause)
        height = page.evaluate("document.body.scrollHeight")
        if height == prev_height:
            break
        prev_height = height


def safe_text(page: Page, selector: str, default: str = "") -> str:
    try:
        el = page.query_selector(selector)
        return el.inner_text().strip() if el else default
    except Exception:
        return default


def scrape_experience(page: Page) -> list:
    items = []
    cards = page.query_selector_all("#experience ~ .pvs-list__outer-container li.artdeco-list__item")
    if not cards:
        cards = page.query_selector_all("section[id*='experience'] li")
    for card in cards:
        text = card.inner_text().strip()
        if not text or len(text) < 5:
            continue
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        entry = {
            "title": lines[0] if len(lines) > 0 else "",
            "company": lines[1] if len(lines) > 1 else "",
            "date_range": lines[2] if len(lines) > 2 else "",
            "location": lines[3] if len(lines) > 3 else "",
            "description": " ".join(lines[4:]) if len(lines) > 4 else "",
            "source": "linkedin",
        }
        items.append(entry)
    return items


def scrape_education(page: Page) -> list:
    items = []
    cards = page.query_selector_all("#education ~ .pvs-list__outer-container li.artdeco-list__item")
    if not cards:
        cards = page.query_selector_all("section[id*='education'] li")
    for card in cards:
        text = card.inner_text().strip()
        if not text or len(text) < 5:
            continue
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        entry = {
            "institution": lines[0] if len(lines) > 0 else "",
            "degree": lines[1] if len(lines) > 1 else "",
            "field_of_study": lines[2] if len(lines) > 2 else "",
            "date_range": lines[3] if len(lines) > 3 else "",
            "source": "linkedin",
        }
        items.append(entry)
    return items


def scrape_skills(page: Page) -> list:
    skills = []
    # Try the skills section
    cards = page.query_selector_all("#skills ~ .pvs-list__outer-container li.artdeco-list__item")
    if not cards:
        cards = page.query_selector_all("section[id*='skills'] li")
    for card in cards:
        text = card.inner_text().strip()
        if not text:
            continue
        name = text.split("\n")[0].strip()
        if name:
            skills.append({"name": name, "endorsements": None, "source": "linkedin"})
    return skills


def scrape_certifications(page: Page) -> list:
    items = []
    cards = page.query_selector_all(
        "#licenses_and_certifications ~ .pvs-list__outer-container li.artdeco-list__item"
    )
    if not cards:
        cards = page.query_selector_all("section[id*='certif'] li")
    for card in cards:
        text = card.inner_text().strip()
        if not text:
            continue
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        entry = {
            "name": lines[0] if len(lines) > 0 else "",
            "issuer": lines[1] if len(lines) > 1 else "",
            "issued_date": lines[2] if len(lines) > 2 else "",
            "source": "linkedin",
        }
        items.append(entry)
    return items


def scrape_languages(page: Page) -> list:
    langs = []
    cards = page.query_selector_all(
        "#languages ~ .pvs-list__outer-container li.artdeco-list__item"
    )
    for card in cards:
        text = card.inner_text().strip()
        if not text:
            continue
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        langs.append({
            "name": lines[0] if len(lines) > 0 else "",
            "proficiency": lines[1] if len(lines) > 1 else None,
        })
    return langs


def scrape_linkedin_profile(
    cookies_path: str = COOKIES_PATH,
    profile_url: str = PROFILE_URL,
    output_path: str = OUTPUT_PATH,
) -> dict:
    if not profile_url:
        raise ValueError(
            "LINKEDIN_PROFILE_URL is not set in .env\n"
            "Set it to your LinkedIn profile URL, e.g.:\n"
            "  LINKEDIN_PROFILE_URL=https://www.linkedin.com/in/john-doe/"
        )

    cookies = load_cookies(cookies_path)
    log.info("Loaded %d cookies from %s", len(cookies), cookies_path)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=300)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        context.add_cookies(cookies)
        page = context.new_page()

        log.info("Loading profile: %s", profile_url)
        page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)

        # Detect login wall
        if "linkedin.com/login" in page.url or "authwall" in page.url:
            browser.close()
            raise LinkedInSessionError(
                "LinkedIn redirected to login page — session expired.\n"
                "Re-run: python tools/save_linkedin_session.py"
            )

        scroll_to_bottom(page)

        # Basic identity
        name = safe_text(page, "h1")
        headline = safe_text(page, ".text-body-medium.break-words")
        location = safe_text(page, ".pb2 .text-body-small.inline.t-black--light.break-words")
        about = safe_text(page, "#about ~ .pvs-list__outer-container .visually-hidden") or \
                safe_text(page, "section[id*='about'] .pv-shared-text-with-see-more span[aria-hidden='true']")

        log.info("Name: %s | Headline: %s", name, headline)

        profile = {
            "meta": {
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "profile_url": profile_url,
            },
            "identity": {
                "full_name": name,
                "headline": headline,
                "location": location,
                "summary": about,
                "linkedin_url": profile_url,
            },
            "experience": scrape_experience(page),
            "education": scrape_education(page),
            "skills": scrape_skills(page),
            "certifications": scrape_certifications(page),
            "languages": scrape_languages(page),
        }

        browser.close()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    log.info(
        "Profile saved to %s — %d experience, %d skills",
        output_path,
        len(profile["experience"]),
        len(profile["skills"]),
    )
    return profile


if __name__ == "__main__":
    scrape_linkedin_profile()
