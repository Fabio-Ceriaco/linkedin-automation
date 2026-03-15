# Generate PDF Report

## Objective
Build a clean, readable PDF job match report from the scored jobs list.

## Required Inputs
- `.tmp/scored_jobs.json` (from `score_jobs.py`)
- `.tmp/master_profile.json` (for candidate name on cover page)

## Run
```bash
python tools/generate_report.py
```

## Output
`.tmp/job_report_YYYY-MM.pdf`

## Report Structure
1. **Cover page**
   - Title: "LinkedIn Job Match Report"
   - Candidate name
   - Number of jobs evaluated
   - Top match score
   - Generation date

2. **One section per job** (sorted by score):
   - Rank badge (`#1`, `#2`, …) + score badge (coloured by score: green ≥70, orange ≥50, grey <50)
   - Job title, company, location, posted date
   - Fit summary (highlighted box)
   - Score rationale
   - Matched skills (green badges)
   - Missing skills (orange badges)
   - Apply URL (clickable link)
   - Contact email (if available)
   - Separator line

3. **Footer** on each page: report title + page number

## Known Constraints
- Requires `reportlab` installed (`pip install reportlab`)
- If `scored_jobs.json` is empty, the tool raises a clear error
- Report filename uses the current month: `job_report_2026-03.pdf`
- Running in the same month will overwrite the previous report

## Troubleshooting
| Problem | Solution |
|---|---|
| `ModuleNotFoundError: reportlab` | `pip install reportlab` |
| PDF is empty or very short | Check that `scored_jobs.json` has entries |
| Candidate name missing | Ensure `master_profile.json` exists with `identity.full_name` |
| Skill badges overflow page | Only first 8 skills per category are shown |
