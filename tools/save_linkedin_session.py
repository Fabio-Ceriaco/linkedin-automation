"""
save_linkedin_session.py
────────────────────────
ONE-TIME SETUP TOOL

Opens a real (headed) browser window so you can log into LinkedIn manually.
Once you're logged in and have dismissed any challenges, press ENTER in the
terminal and the script saves your session cookies to LINKEDIN_COOKIES_PATH.

Run this again whenever your session expires (every 30-90 days).

Usage:
    python tools/save_linkedin_session.py
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

COOKIES_PATH = os.getenv("LINKEDIN_COOKIES_PATH", ".tmp/linkedin_cookies.json")


def save_session(cookies_path: str = COOKIES_PATH) -> None:
    output = Path(cookies_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("LinkedIn Session Setup")
    print("=" * 60)
    print()
    print("A browser window will open. Please:")
    print("  1. Log into LinkedIn as normal")
    print("  2. Complete any 2FA or security challenges")
    print("  3. Wait until you see your LinkedIn feed")
    print("  4. Come back here and press ENTER")
    print()
    input("Press ENTER to open the browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.goto("https://www.linkedin.com/login")

        print()
        print("Browser is open. Log in now, then come back here.")
        print()
        input("Once you see your LinkedIn feed, press ENTER to save the session...")

        cookies = context.cookies()
        if not cookies:
            print("ERROR: No cookies found. Did you log in successfully?")
            browser.close()
            sys.exit(1)

        with open(output, "w") as f:
            json.dump(cookies, f, indent=2)

        browser.close()

    print()
    print(f"Session saved to: {output}")
    print(f"Cookies count: {len(cookies)}")
    print()
    print("You can now run the full pipeline. This session will last 30-90 days.")
    print("If Playwright is ever redirected to a login page, re-run this script.")


if __name__ == "__main__":
    save_session()
