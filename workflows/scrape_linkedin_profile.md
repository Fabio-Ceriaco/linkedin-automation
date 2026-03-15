# Scrape LinkedIn Profile

## Objective
Use Playwright with saved cookies to scrape the user's LinkedIn profile into structured JSON.

## Required Inputs
- `.tmp/linkedin_cookies.json` (from `setup_linkedin_session.md`)
- `LINKEDIN_PROFILE_URL` in `.env` (your full LinkedIn profile URL)

## Run
```bash
python tools/scrape_linkedin_profile.py
```

## Output
`.tmp/linkedin_profile.json` containing:
- `identity`: name, headline, location, summary, LinkedIn URL
- `experience[]`: title, company, date_range, location, description
- `education[]`: institution, degree, field_of_study, date_range
- `skills[]`: name, endorsements, source
- `certifications[]`: name, issuer, issued_date
- `languages[]`: name, proficiency

## Known Constraints
- LinkedIn uses dynamic class names that change. Selectors use ARIA roles and data attributes where possible.
- Headless scraping may occasionally fail if LinkedIn detects automation. Re-save the session if this happens.
- The `about` section requires scrolling to load — the tool scrolls to the bottom before scraping.
- Skills section may only show the first 5 skills unless "Show all" is expanded. The tool attempts to read all visible skills.

## Troubleshooting
| Problem | Solution |
|---|---|
| Redirected to login | Re-run `save_linkedin_session.py` |
| Empty experience/skills | LinkedIn changed selectors — run with `headless=False` and inspect DOM |
| Profile URL not found | Check `LINKEDIN_PROFILE_URL` in `.env` — use exact URL from your browser |
