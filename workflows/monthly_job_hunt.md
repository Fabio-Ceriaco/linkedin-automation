# Monthly Job Hunt Pipeline

## Objective
Run the full 7-step pipeline to scrape your profile, search for jobs, score them with AI, and deliver a ranked PDF report to your inbox.

## Required Inputs (before first run)
- [ ] `.env` file fully populated (see `.env` for all keys)
- [ ] LinkedIn session saved: `.tmp/linkedin_cookies.json` (run `setup_linkedin_session.md`)
- [ ] CV PDF accessible at the path set in `CV_PDF_PATH`
- [ ] `ANTHROPIC_API_KEY` set and valid
- [ ] `GMAIL_APP_PASSWORD` set (Google Account → Security → App Passwords)

## Run the Pipeline

### Full run (recommended):
```bash
python orchestrator.py
```

### Development shortcuts (skip expensive steps when iterating):
```bash
# Skip LinkedIn & CV scraping — reuse existing master_profile.json
python orchestrator.py --skip-profile

# Skip job scraping — reuse existing raw_jobs.json (fast iteration on scoring/report)
python orchestrator.py --skip-jobs

# Generate and preview the PDF without sending the email
python orchestrator.py --dry-run

# Combine flags
python orchestrator.py --skip-profile --skip-jobs --dry-run
```

## Pipeline Steps

| Step | Tool | Input | Output |
|---|---|---|---|
| 1 | `scrape_linkedin_profile.py` | cookies + profile URL | `.tmp/linkedin_profile.json` |
| 2 | `parse_cv.py` | PDF at `CV_PDF_PATH` | `.tmp/cv_data.json` |
| 3 | `build_master_profile.py` | both JSONs above | `.tmp/master_profile.json` |
| 4 | `scrape_jobs.py` | cookies + keywords | `.tmp/raw_jobs.json` |
| 5 | `score_jobs.py` | master profile + raw jobs | `.tmp/scored_jobs.json` |
| 6 | `generate_report.py` | scored jobs | `.tmp/job_report_YYYY-MM.pdf` |
| 7 | `send_email.py` | PDF + Gmail creds | Email delivered |

## Expected Output
- A PDF report in your inbox titled "LinkedIn Job Match Report — [Month] [Year]"
- The PDF contains up to `TOP_JOBS_IN_REPORT` jobs ranked by AI fit score
- Each job includes: score, fit summary, rationale, matched/missing skills, apply link, contact email

## Edge Cases

### Session expired (step 1 or 4 fails with login redirect)
Re-run the session setup:
```bash
python tools/save_linkedin_session.py
```
Then retry the pipeline with `--skip-profile` if profile data is still fresh:
```bash
python orchestrator.py --skip-profile
```

### CV parsing fails (< 100 chars extracted)
- Check `.tmp/cv_raw_text.txt` to see what was extracted
- If the PDF is scanned/image-only, export it as a text-based PDF from Word or Google Docs
- Then re-run: `python tools/parse_cv.py`

### Zero jobs scraped (step 4)
- Verify `JOB_SEARCH_KEYWORDS` and `JOB_SEARCH_LOCATION` in `.env`
- Try running with `headless=False` to watch the browser (change line in `scrape_jobs.py` temporarily)
- LinkedIn may have changed selectors — check `.tmp/raw_jobs.json` and update selectors in `scrape_jobs.py`

### Claude API error (step 5)
- Check `ANTHROPIC_API_KEY` is valid at console.anthropic.com
- If rate limited, wait a minute and re-run with `--skip-jobs`

### Email delivery fails (step 7)
- Verify `GMAIL_APP_PASSWORD` is a 16-character App Password, not your account password
- Check Google Account → Security → App Passwords
- Re-run just the email step: `python tools/send_email.py`

## Logs
All pipeline output is written to `.tmp/pipeline.log`. Check it for debugging:
```bash
tail -100 .tmp/pipeline.log
```

## Monthly Schedule
The pipeline runs automatically on the 1st of each month via cron.
To set this up: `python scheduler.py --install`
To check status: `python scheduler.py --status`
