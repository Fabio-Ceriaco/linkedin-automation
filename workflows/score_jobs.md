# Score Jobs with Claude

## Objective
Use the Claude API to score each raw job listing (0-100) against the master profile and extract structured match data.

## Required Inputs
- `.tmp/master_profile.json` (from `build_master_profile.py`)
- `.tmp/raw_jobs.json` (from `scrape_jobs.py`)
- `ANTHROPIC_API_KEY` in `.env`

## Run
```bash
python tools/score_jobs.py
```

## Output
`.tmp/scored_jobs.json` — top `TOP_JOBS_IN_REPORT` jobs sorted by score descending, each with:
- All fields from `raw_jobs.json`
- `score` (0-100 integer)
- `score_rationale` (2-3 sentence explanation)
- `matched_skills` (list of matching skills)
- `missing_skills` (list of skills the job requires but candidate lacks)
- `fit_summary` (one-sentence headline for the report)

## How It Works
1. Loads `master_profile.json` and extracts `profile_text_for_matching` (4000-char prose)
2. For each job, sends a structured prompt to `claude-haiku-4-5-20251001`
3. Parses the JSON response (strips markdown fences if present)
4. On JSON parse failure, retries once with a stricter prompt
5. Sorts all results by score descending
6. Keeps the top `TOP_JOBS_IN_REPORT` entries

## Cost Estimate
- Model: `claude-haiku-4-5-20251001` (cheapest Claude model)
- ~1500 tokens per job call
- 30 jobs × $0.80/MTok input + $4/MTok output ≈ **~$0.05 per run**
- Reduce `JOB_SEARCH_MAX_RESULTS` to lower this further

## Known Constraints
- 0.4s delay between API calls to stay within rate limits
- On `RateLimitError`, the tool waits 60s and retries
- Profile text is capped at 4000 chars — ensure `build_master_profile.py` ran successfully
- Jobs with very short descriptions (< 50 chars) may receive low/inaccurate scores

## Troubleshooting
| Problem | Solution |
|---|---|
| `ANTHROPIC_API_KEY` error | Set key in `.env` (console.anthropic.com → API Keys) |
| All jobs score 0 | Check `profile_text_for_matching` is populated in `master_profile.json` |
| JSON parse errors on many jobs | Claude may be returning malformed JSON; check API response and adjust prompt if needed |
| Rate limit errors | Reduce batch size or add more sleep between calls |
