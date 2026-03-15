# Scrape LinkedIn Jobs

## Objective
Use Playwright with saved cookies to search LinkedIn Jobs and scrape listings matching the configured keywords and location.

## Required Inputs
- `.tmp/linkedin_cookies.json` (from `setup_linkedin_session.md`)
- `JOB_SEARCH_KEYWORDS` in `.env` — comma-separated, e.g. `Python Engineer,Backend Developer`
- `JOB_SEARCH_LOCATION` in `.env` — e.g. `Remote` or `London, UK`
- `JOB_SEARCH_MAX_RESULTS` in `.env` — max listings to scrape (keep ≤ 50)

## Run
```bash
python tools/scrape_jobs.py
```

## Output
`.tmp/raw_jobs.json` — list of job objects, each with:
- `job_id`, `title`, `company`, `location`, `posted_date`
- `description` (up to 3000 chars)
- `apply_url` — direct LinkedIn job URL
- `contact_email` — extracted from description text if present
- `scraped_at` — timestamp

## How It Works
1. Loads cookies and launches headless Chromium
2. For each keyword, navigates to LinkedIn Jobs search with a 30-day recency filter
3. Scrolls the job list panel to load more cards
4. Clicks each card, waits for the detail panel to load, extracts all fields
5. Deduplicates by `job_id` across all keywords
6. Saves to `raw_jobs.json`

## Known Constraints
- LinkedIn changes CSS class names frequently. The tool uses `data-job-id` attributes and ARIA roles to reduce breakage.
- `slow_mo=500` and randomised waits between card clicks reduce bot detection.
- After ~50 job views in one session, LinkedIn may throttle or block. Keep `JOB_SEARCH_MAX_RESULTS ≤ 50`.
- Jobs posted more than 30 days ago are filtered out via `f_TPR=r2592000`.
- Contact emails are rare in job descriptions but extracted when found.

## Troubleshooting
| Problem | Solution |
|---|---|
| Zero jobs scraped | Check keywords/location in `.env`; temporarily set `headless=False` in `scrape_jobs.py` to watch |
| Redirected to login | Re-run `save_linkedin_session.py` |
| CaptchaError | Session flagged as bot. Re-save session from a fresh manual login; wait a few hours |
| Missing job titles | LinkedIn changed selectors. Inspect DOM with `headless=False` and update selectors in `extract_job_detail()` |
| Only 1-2 jobs found | LinkedIn may be paginating; increase scroll iterations in `scroll_job_list()` |

## Selector Reference (may need updating over time)
```
Job cards:     li.jobs-search-results__list-item
Job ID attr:   data-occludable-job-id or data-job-id
Title:         h1.job-details-jobs-unified-top-card__job-title
Company:       .job-details-jobs-unified-top-card__company-name
Location:      .job-details-jobs-unified-top-card__bullet
Description:   .jobs-description__content or #job-details
```
When selectors break, compare against the current LinkedIn DOM and update `extract_job_detail()` in `scrape_jobs.py`.
