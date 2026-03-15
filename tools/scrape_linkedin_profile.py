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
    return page.evaluate("""() => {
        const section = document.querySelector("div[componentkey*='ExperienceTopLevelSection'] section");
        if (!section) return [];
        const jobs = [];
        const links = section.querySelectorAll("a[href*='/edit/forms/position/']");
        for (const link of links) {
            const ps = link.querySelectorAll('p');
            const title = ps[0]?.textContent?.trim() || '';
            if (!title) continue;
            const companyRaw = ps[1]?.textContent?.trim() || '';
            const company = companyRaw.split('\\u00b7')[0].trim();
            const dateRange = ps[2]?.textContent?.trim() || '';
            const location = ps[3]?.textContent?.trim() || '';
            const descEl = link.parentElement?.querySelector('span[data-testid="expandable-text-box"]');
            const description = descEl?.textContent?.trim() || '';
            jobs.push({ title, company, date_range: dateRange, location, description, source: 'linkedin' });
        }
        return jobs;
    }""")


def scrape_education(page: Page) -> list:
    return page.evaluate("""() => {
        const section = document.querySelector("div[componentkey*='EducationTopLevelSection'] section");
        if (!section) return [];
        const items = [];
        // Education edit links are under /details/education/edit/forms/
        const links = section.querySelectorAll("a[href*='/details/education/edit/forms/']");
        for (const link of links) {
            const ps = link.querySelectorAll('p');
            const institution = ps[0]?.textContent?.trim() || '';
            if (!institution) continue;
            const degree = ps[1]?.textContent?.trim() || '';
            const field = ps[2]?.textContent?.trim() || '';
            const dateRange = ps[3]?.textContent?.trim() || '';
            items.push({ institution, degree, field_of_study: field, date_range: dateRange, source: 'linkedin' });
        }
        return items;
    }""")


def scrape_skills(page: Page) -> list:
    names = page.evaluate("""() => {
        const items = document.querySelectorAll("div[componentkey*='profile.skill(']");
        const skills = [];
        for (const item of items) {
            const p = item.querySelector('p');
            const name = p?.textContent?.trim();
            if (name && name.length > 1) skills.push(name);
        }
        return [...new Set(skills)];
    }""")
    return [{"name": n, "endorsements": None, "source": "linkedin"} for n in names]


def scrape_certifications(page: Page) -> list:
    return page.evaluate("""() => {
        const section = document.querySelector("div[componentkey*='CertificationTopLevel'] section");
        if (!section) return [];
        const items = [];
        const links = section.querySelectorAll("a[href*='/edit/forms/certification/']");
        for (const link of links) {
            const ps = link.querySelectorAll('p');
            const name = ps[0]?.textContent?.trim() || '';
            if (!name) continue;
            const issuer = ps[1]?.textContent?.trim() || '';
            const issued_date = ps[2]?.textContent?.trim() || '';
            items.push({ name, issuer, issued_date, source: 'linkedin' });
        }
        return items;
    }""")


def scrape_languages(page: Page) -> list:
    return page.evaluate("""() => {
        const section = document.querySelector("div[componentkey*='LanguageTopLevel'] section");
        if (!section) return [];
        const langs = [];
        const links = section.querySelectorAll("a[href*='/edit/forms/language/']");
        for (const link of links) {
            const ps = link.querySelectorAll('p');
            const name = ps[0]?.textContent?.trim() || '';
            if (!name) continue;
            const proficiency = ps[1]?.textContent?.trim() || null;
            langs.push({ name, proficiency });
        }
        return langs;
    }""")
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

        # Basic identity — uses componentkey-based selectors (stable across LinkedIn redesigns)
        name = safe_text(page, "div[componentkey*='Topcard'] h2")
        # Headline and location: first two meaningful p elements after the name h2 in Topcard
        headline, location = page.evaluate("""() => {
            const topcard = document.querySelector("div[componentkey*='Topcard']");
            if (!topcard) return ['', ''];
            const allP = Array.from(topcard.querySelectorAll('p'));
            const texts = allP
                .map(p => p.textContent.trim())
                .filter(t => t.length > 3 && t !== '.' && !t.match(/^\\d+ connections/));
            return [texts[0] || '', texts[1] || ''];
        }""")
        about = safe_text(page, "div[componentkey*='About'] span[data-testid='expandable-text-box']")

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
