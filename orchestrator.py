"""
orchestrator.py
───────────────
Runs the full LinkedIn job-hunt pipeline in sequence.

Pipeline steps:
  1. Scrape LinkedIn profile (Playwright + saved cookies)
  2. Parse PDF CV
  3. Build master profile (merge LinkedIn + CV)
  4. Scrape LinkedIn job listings (Playwright + saved cookies)
  5. Score jobs with Claude API
  6. Generate PDF report
  7. Send report via Gmail

Usage:
    python orchestrator.py                  # Full run
    python orchestrator.py --skip-profile   # Skip steps 1-3 (reuse existing master_profile.json)
    python orchestrator.py --skip-cv        # Skip CV parsing (reuse existing cv_data.json)
    python orchestrator.py --skip-profile --skip-cv  # Jump straight to job scraping
    python orchestrator.py --skip-jobs      # Skip scraping, reuse existing raw_jobs.json
    python orchestrator.py --dry-run        # Run everything except sending the email
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(".tmp/pipeline.log", mode="a"),
    ],
)
log = logging.getLogger("orchestrator")


def ensure_cookies_exist() -> None:
    cookies_path = os.getenv("LINKEDIN_COOKIES_PATH", ".tmp/linkedin_cookies.json")
    if not Path(cookies_path).exists():
        log.error(
            "LinkedIn session cookies not found: %s\n"
            "Run this first: python tools/save_linkedin_session.py",
            cookies_path,
        )
        sys.exit(1)


def run_pipeline(
    skip_profile: bool = False,
    skip_cv: bool = False,
    skip_jobs: bool = False,
    dry_run: bool = False,
) -> None:
    from tools.scrape_linkedin_profile import scrape_linkedin_profile
    from tools.parse_cv import parse_cv
    from tools.build_master_profile import build_master_profile
    from tools.scrape_jobs import scrape_jobs
    from tools.score_jobs import score_jobs
    from tools.generate_report import generate_report
    from tools.send_email import send_email

    Path(".tmp").mkdir(exist_ok=True)

    log.info("=" * 60)
    log.info("LinkedIn Job Hunt Pipeline — starting")
    log.info("=" * 60)

    # ── Step 1: Scrape LinkedIn profile ──────────────────────────────────────
    if not skip_profile:
        log.info("[1/7] Scraping LinkedIn profile...")
        ensure_cookies_exist()
        scrape_linkedin_profile()
    else:
        log.info("[1/7] Skipped (--skip-profile)")

    # ── Step 2: Parse CV ──────────────────────────────────────────────────────
    if not skip_cv:
        log.info("[2/7] Parsing CV PDF...")
        parse_cv()
    else:
        log.info("[2/7] Skipped (--skip-cv)")

    # ── Step 3: Build master profile ─────────────────────────────────────────
    if not skip_profile and not skip_cv:
        log.info("[3/7] Building master profile...")
        build_master_profile()
    elif not Path(".tmp/master_profile.json").exists():
        log.info("[3/7] Building master profile from available data...")
        build_master_profile()
    else:
        log.info("[3/7] Reusing existing master_profile.json")

    # ── Step 4: Scrape jobs ───────────────────────────────────────────────────
    if not skip_jobs:
        log.info("[4/7] Scraping LinkedIn jobs...")
        ensure_cookies_exist()
        keywords_raw = os.getenv("JOB_SEARCH_KEYWORDS", "")
        keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
        scrape_jobs(
            keywords=keywords,
            location=os.getenv("JOB_SEARCH_LOCATION", "Remote"),
            max_results=int(os.getenv("JOB_SEARCH_MAX_RESULTS", "30")),
        )
    else:
        log.info("[4/7] Skipped (--skip-jobs)")

    # ── Step 5: Score jobs ────────────────────────────────────────────────────
    log.info("[5/7] Scoring jobs with Claude...")
    scored = score_jobs(top_n=int(os.getenv("TOP_JOBS_IN_REPORT", "15")))

    # ── Step 6: Generate PDF ──────────────────────────────────────────────────
    log.info("[6/7] Generating PDF report...")
    pdf_path = generate_report(output_dir=os.getenv("REPORT_OUTPUT_DIR", ".tmp"))

    # ── Step 7: Send email ────────────────────────────────────────────────────
    if not dry_run:
        log.info("[7/7] Sending report via email...")
        top_job = scored[0] if scored else None
        send_email(pdf_path=pdf_path, top_job=top_job)
    else:
        log.info("[7/7] Skipped (--dry-run) — PDF saved at: %s", pdf_path)

    log.info("=" * 60)
    log.info("Pipeline complete. PDF: %s", pdf_path)
    log.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="LinkedIn Job Hunt Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python orchestrator.py                   # full run\n"
            "  python orchestrator.py --skip-profile    # skip LinkedIn profile scraping\n"
            "  python orchestrator.py --skip-jobs       # skip job scraping, reuse raw_jobs.json\n"
            "  python orchestrator.py --dry-run         # full run but don't send email\n"
        ),
    )
    parser.add_argument(
        "--skip-profile",
        action="store_true",
        help="Skip LinkedIn profile scraping and CV parsing; reuse existing data",
    )
    parser.add_argument(
        "--skip-cv",
        action="store_true",
        help="Skip CV parsing; reuse existing cv_data.json",
    )
    parser.add_argument(
        "--skip-jobs",
        action="store_true",
        help="Skip job scraping; reuse existing raw_jobs.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run all steps but do not send the email",
    )
    args = parser.parse_args()

    try:
        run_pipeline(
            skip_profile=args.skip_profile,
            skip_cv=args.skip_cv,
            skip_jobs=args.skip_jobs,
            dry_run=args.dry_run,
        )
    except KeyboardInterrupt:
        log.info("Pipeline interrupted by user.")
        sys.exit(0)
    except Exception as e:
        log.error("Pipeline failed: %s", e, exc_info=True)
        sys.exit(1)
