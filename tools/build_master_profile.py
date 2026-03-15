"""
build_master_profile.py
───────────────────────
Merges linkedin_profile.json and cv_data.json into a single master_profile.json.

Merge rules:
- LinkedIn data is authoritative for structured fields.
- CV fills gaps and adds entries not in LinkedIn (fuzzy-matched by company name).
- Skills are unioned; LinkedIn skills keep endorsement counts.
- profile_text_for_matching is a capped prose string for Claude scoring.

Usage:
    python tools/build_master_profile.py
"""

import json
import logging
import os
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

LINKEDIN_PATH = ".tmp/linkedin_profile.json"
CV_PATH = ".tmp/cv_data.json"
OUTPUT_PATH = ".tmp/master_profile.json"
PROFILE_TEXT_MAX_CHARS = 4000

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_master_profile")


class MergeError(Exception):
    pass


def load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise MergeError(f"Required file not found: {path}")
    with open(p) as f:
        return json.load(f)


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def merge_experience(li_exp: list, cv_exp: list) -> list:
    merged = []
    used_cv_indices = set()

    for li_entry in li_exp:
        li_company = li_entry.get("company", "")
        best_match_idx = None
        best_score = 0.0

        for i, cv_entry in enumerate(cv_exp):
            if i in used_cv_indices:
                continue
            cv_company = cv_entry.get("company", "")
            score = similarity(li_company, cv_company)
            if score > best_score:
                best_score = score
                best_match_idx = i

        if best_match_idx is not None and best_score >= 0.7:
            cv_entry = cv_exp[best_match_idx]
            used_cv_indices.add(best_match_idx)
            # Use LinkedIn's structured data, prefer longer description
            li_desc = li_entry.get("description", "") or ""
            cv_desc = cv_entry.get("description", "") or ""
            description = li_desc if len(li_desc) >= len(cv_desc) else cv_desc
            merged.append({**li_entry, "description": description, "source": "merged"})
        else:
            merged.append(li_entry)

    # Add CV-only entries
    for i, cv_entry in enumerate(cv_exp):
        if i not in used_cv_indices:
            merged.append(cv_entry)

    return merged


def merge_education(li_edu: list, cv_edu: list) -> list:
    merged = []
    used_cv_indices = set()

    for li_entry in li_edu:
        li_inst = li_entry.get("institution", "")
        best_match_idx = None
        best_score = 0.0
        for i, cv_entry in enumerate(cv_edu):
            if i in used_cv_indices:
                continue
            score = similarity(li_inst, cv_entry.get("institution", ""))
            if score > best_score:
                best_score = score
                best_match_idx = i
        if best_match_idx is not None and best_score >= 0.7:
            used_cv_indices.add(best_match_idx)
            merged.append({**li_entry, "source": "merged"})
        else:
            merged.append(li_entry)

    for i, cv_entry in enumerate(cv_edu):
        if i not in used_cv_indices:
            # Skip garbled entries where institution looks like a bullet point or skill
            inst = cv_entry.get("institution", "")
            if inst.startswith("●") or inst.startswith("○") or inst.startswith("•"):
                continue
            merged.append(cv_entry)

    return merged


def merge_skills(li_skills: list, cv_skills: list) -> list:
    seen = {}
    for s in li_skills:
        key = s["name"].lower().strip()
        seen[key] = s

    for s in cv_skills:
        key = s["name"].lower().strip()
        if key not in seen:
            seen[key] = s

    return list(seen.values())


def build_profile_text(profile: dict) -> str:
    parts = []

    identity = profile.get("identity", {})
    if identity.get("headline"):
        parts.append(identity["headline"])
    if identity.get("summary"):
        parts.append(identity["summary"])

    for exp in profile.get("experience", []):
        title = exp.get("title", "")
        company = exp.get("company", "")
        desc = exp.get("description", "") or ""
        date = exp.get("date_range", "")
        line = f"{title} at {company} ({date}). {desc}".strip()
        parts.append(line)

    for edu in profile.get("education", []):
        degree = edu.get("degree", "")
        inst = edu.get("institution", "")
        field = edu.get("field_of_study", "")
        parts.append(f"{degree} {field} at {inst}".strip())

    skill_names = [s["name"] for s in profile.get("skills", [])]
    if skill_names:
        parts.append("Skills: " + ", ".join(skill_names))

    for cert in profile.get("certifications", []):
        parts.append(f"Certification: {cert.get('name', '')}")

    text = " ".join(parts)
    return text[:PROFILE_TEXT_MAX_CHARS]


def build_master_profile(
    linkedin_path: str = LINKEDIN_PATH,
    cv_path: str = CV_PATH,
    output_path: str = OUTPUT_PATH,
) -> dict:
    log.info("Loading LinkedIn profile from %s", linkedin_path)
    li = load_json(linkedin_path)

    log.info("Loading CV data from %s", cv_path)
    cv = load_json(cv_path)

    li_identity = li.get("identity", {})
    cv_identity = cv.get("identity", {})

    # Prefer LinkedIn for most fields; fill gaps from CV
    identity = {
        "full_name": li_identity.get("full_name") or cv_identity.get("full_name", ""),
        "headline": li_identity.get("headline", ""),
        "location": li_identity.get("location") or cv_identity.get("location", ""),
        "email": cv_identity.get("email") or li_identity.get("email"),
        "linkedin_url": li_identity.get("linkedin_url", ""),
        "summary": li_identity.get("summary") or cv_identity.get("summary", ""),
    }

    experience = merge_experience(
        li.get("experience", []), cv.get("experience", [])
    )
    education = merge_education(
        li.get("education", []), cv.get("education", [])
    )
    skills = merge_skills(
        li.get("skills", []), cv.get("skills", [])
    )

    # Prefer LinkedIn certs; add CV-only ones
    li_certs = li.get("certifications", [])
    cv_certs = cv.get("certifications", [])
    cert_names = {c["name"].lower() for c in li_certs}
    certifications = li_certs + [
        c for c in cv_certs if c["name"].lower() not in cert_names
    ]

    li_langs = li.get("languages", []) or []
    cv_langs = cv.get("languages", []) or []
    # Clean bullet prefixes from CV language names
    cleaned_cv_langs = [
        {**l, "name": l["name"].lstrip("● ").strip()} for l in cv_langs
    ]
    li_lang_names = {l["name"].lower() for l in li_langs}
    extra_cv_langs = [l for l in cleaned_cv_langs if l["name"].lower() not in li_lang_names]
    languages = li_langs + extra_cv_langs
    projects = cv.get("projects", []) or []

    profile = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "linkedin_scraped_at": li.get("meta", {}).get("scraped_at"),
            "cv_parsed_at": cv.get("meta", {}).get("parsed_at"),
        },
        "identity": identity,
        "experience": experience,
        "education": education,
        "skills": skills,
        "certifications": certifications,
        "languages": languages,
        "projects": projects,
    }

    profile["profile_text_for_matching"] = build_profile_text(profile)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    log.info(
        "Master profile saved to %s — %d exp, %d skills, %d edu | text: %d chars",
        output_path,
        len(experience),
        len(skills),
        len(education),
        len(profile["profile_text_for_matching"]),
    )
    return profile


if __name__ == "__main__":
    build_master_profile()
