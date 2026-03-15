"""
score_jobs.py
─────────────
Uses Claude API to score each raw job listing against the master profile.

For each job, sends a structured prompt and parses a JSON response containing:
  - score (0-100)
  - score_rationale (2-3 sentences)
  - matched_skills (list)
  - missing_skills (list)
  - fit_summary (1 sentence headline)

Results are sorted by score descending and the top N are saved.

Usage:
    python tools/score_jobs.py
"""

import json
import logging
import os
import re
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

MASTER_PROFILE_PATH = ".tmp/master_profile.json"
RAW_JOBS_PATH = ".tmp/raw_jobs.json"
OUTPUT_PATH = ".tmp/scored_jobs.json"
TOP_N = int(os.getenv("TOP_JOBS_IN_REPORT", "15"))
MODEL = "claude-haiku-4-5-20251001"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("score_jobs")

SYSTEM_PROMPT = (
    "You are a professional career advisor. Evaluate job-candidate fit precisely and numerically. "
    "Return ONLY valid JSON — no markdown, no explanation outside the JSON object."
)

JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]+?)\s*```")


def load_json(path: str) -> dict | list:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with open(p) as f:
        return json.load(f)


def build_prompt(profile_text: str, job: dict) -> str:
    description = (job.get("description") or "")[:2500]
    return (
        f"## Candidate Profile\n{profile_text}\n\n"
        f"## Job Listing\n"
        f"Title: {job.get('title', '')}\n"
        f"Company: {job.get('company', '')}\n"
        f"Location: {job.get('location', '')}\n"
        f"Description:\n{description}\n\n"
        f"## Task\n"
        f"Score this job from 0 to 100 for fit with the candidate profile.\n"
        f"Return ONLY a JSON object with these exact keys:\n"
        f"  score (integer 0-100)\n"
        f"  score_rationale (string, 2-3 sentences explaining the score)\n"
        f"  matched_skills (list of strings — skills from the profile that match)\n"
        f"  missing_skills (list of strings — skills the job requires but candidate lacks)\n"
        f"  fit_summary (string, one sentence headline for a report)\n"
        f"\nReturn ONLY the JSON object, nothing else."
    )


def parse_claude_response(content: str) -> dict:
    # Strip markdown fences if present
    fence_match = JSON_FENCE_RE.search(content)
    if fence_match:
        content = fence_match.group(1)
    return json.loads(content.strip())


def score_single_job(
    client: anthropic.Anthropic,
    profile_text: str,
    job: dict,
    retry: bool = True,
) -> dict | None:
    prompt = build_prompt(profile_text, job)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        result = parse_claude_response(raw)
        return result
    except json.JSONDecodeError:
        if retry:
            log.warning("JSON parse failed for job %s — retrying with stricter prompt", job.get("job_id"))
            time.sleep(1)
            return score_single_job(client, profile_text, job, retry=False)
        log.error("Could not parse Claude response for job %s", job.get("job_id"))
        return None
    except anthropic.RateLimitError:
        log.warning("Rate limit hit — waiting 60s")
        time.sleep(60)
        return score_single_job(client, profile_text, job, retry=False)
    except Exception as e:
        log.error("Error scoring job %s: %s", job.get("job_id"), e)
        return None


def score_jobs(
    master_profile_path: str = MASTER_PROFILE_PATH,
    raw_jobs_path: str = RAW_JOBS_PATH,
    output_path: str = OUTPUT_PATH,
    top_n: int = TOP_N,
    model: str = MODEL,
) -> list[dict]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY is not set in .env\n"
            "Get your key at console.anthropic.com → API Keys"
        )

    log.info("Loading master profile from %s", master_profile_path)
    profile = load_json(master_profile_path)
    profile_text = profile.get("profile_text_for_matching", "")
    if len(profile_text) < 50:
        raise ValueError(
            "profile_text_for_matching is too short — re-run build_master_profile.py"
        )

    log.info("Loading raw jobs from %s", raw_jobs_path)
    raw_jobs = load_json(raw_jobs_path)
    if not raw_jobs:
        raise ValueError("raw_jobs.json is empty — re-run scrape_jobs.py")

    log.info("Scoring %d jobs with %s (top %d will be kept)...", len(raw_jobs), model, top_n)
    client = anthropic.Anthropic(api_key=api_key)

    scored = []
    for i, job in enumerate(raw_jobs, 1):
        log.info("[%d/%d] Scoring: %s @ %s", i, len(raw_jobs), job.get("title"), job.get("company"))
        result = score_single_job(client, profile_text, job)
        if result:
            scored_job = {**job, **result}
            scored.append(scored_job)
        time.sleep(0.4)  # gentle rate limit

    if not scored:
        raise RuntimeError("No jobs were successfully scored.")

    scored.sort(key=lambda j: j.get("score", 0), reverse=True)
    top_jobs = scored[:top_n]

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(top_jobs, f, indent=2, ensure_ascii=False)

    log.info(
        "Scored %d jobs, saved top %d to %s (top score: %s/100)",
        len(scored),
        len(top_jobs),
        output_path,
        top_jobs[0].get("score") if top_jobs else "N/A",
    )
    return top_jobs


if __name__ == "__main__":
    score_jobs()
