"""
parse_cv.py
───────────
Extracts structured data from a PDF CV using pdfplumber.

Detects common section headers (EXPERIENCE, EDUCATION, SKILLS, etc.)
and parses each section into structured entries.

Raw extracted text is always saved to .tmp/cv_raw_text.txt for inspection.

Usage:
    python tools/parse_cv.py
    python tools/parse_cv.py --cv-path /path/to/my_cv.pdf
"""

import argparse
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
from dotenv import load_dotenv

load_dotenv()

CV_PDF_PATH = os.getenv("CV_PDF_PATH", "")
OUTPUT_PATH = ".tmp/cv_data.json"
RAW_TEXT_PATH = ".tmp/cv_raw_text.txt"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("parse_cv")

# Section header keywords (case-insensitive)
SECTION_HEADERS = {
    "experience": re.compile(
        r"^(work\s+)?experience|employment|professional\s+background|career", re.I
    ),
    "education": re.compile(r"^education|academic|qualifications?|degrees?", re.I),
    "skills": re.compile(r"^(technical\s+)?skills|competenc|technologies|tools", re.I),
    "certifications": re.compile(
        r"^certif|licens|accreditation|credentials?|courses?", re.I
    ),
    "projects": re.compile(r"^projects?|portfolio|work samples?", re.I),
    "languages": re.compile(r"^languages?|spoken\s+languages?", re.I),
    "summary": re.compile(r"^(professional\s+)?(summary|profile|objective|about)", re.I),
    "contact": re.compile(r"^contact|personal\s+info", re.I),
}

DATE_PATTERN = re.compile(
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,]*\d{4}"
    r"|\d{4}\s*[-–]\s*(\d{4}|present|current|now)"
    r"|\d{4}",
    re.I,
)

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"[\+]?[\d\s\-\(\)]{7,15}")


class CVParseError(Exception):
    pass


def extract_text(cv_path: str) -> str:
    path = Path(cv_path)
    if not path.exists():
        raise CVParseError(f"CV file not found: {cv_path}")
    if path.suffix.lower() != ".pdf":
        raise CVParseError(f"Expected a PDF file, got: {path.suffix}")

    pages_text = []
    with pdfplumber.open(cv_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)

    full_text = "\n".join(pages_text)
    if len(full_text.strip()) < 100:
        raise CVParseError(
            "PDF appears to be image-only or text extraction failed (< 100 chars). "
            "Convert the PDF to a text-based PDF before running."
        )
    return full_text


def detect_sections(lines: list[str]) -> dict[str, list[str]]:
    """Split lines into named sections based on header detection."""
    sections: dict[str, list[str]] = {"header": []}
    current = "header"

    for line in lines:
        stripped = line.strip()
        if not stripped:
            sections.setdefault(current, []).append("")
            continue

        matched = False
        for section_name, pattern in SECTION_HEADERS.items():
            if pattern.match(stripped) and len(stripped) < 60:
                current = section_name
                sections.setdefault(current, [])
                matched = True
                break

        if not matched:
            sections.setdefault(current, []).append(stripped)

    return sections


def parse_contact_from_header(lines: list[str]) -> dict:
    contact = {"full_name": "", "email": None, "phone": None, "location": ""}
    non_empty = [l for l in lines if l.strip()]
    if non_empty:
        contact["full_name"] = non_empty[0]

    all_text = " ".join(lines)
    email_match = EMAIL_PATTERN.search(all_text)
    if email_match:
        contact["email"] = email_match.group()

    for line in non_empty[1:]:
        if not EMAIL_PATTERN.search(line) and not DATE_PATTERN.search(line):
            if len(line) > 3 and not line.startswith("http"):
                contact["location"] = line
                break

    return contact


def parse_experience(lines: list[str]) -> list[dict]:
    entries = []
    current: dict | None = None

    for line in lines:
        if not line.strip():
            continue
        date_match = DATE_PATTERN.search(line)
        # Heuristic: a line with a date that's short is likely a job header
        if date_match and len(line) < 80:
            if current:
                entries.append(current)
            current = {
                "title": "",
                "company": "",
                "date_range": line.strip(),
                "description": "",
                "source": "cv",
            }
        elif current is None:
            # First non-date line is the job title
            current = {
                "title": line.strip(),
                "company": "",
                "date_range": "",
                "description": "",
                "source": "cv",
            }
        elif not current["company"]:
            current["company"] = line.strip()
        else:
            current["description"] = (current["description"] + " " + line).strip()

    if current:
        entries.append(current)
    return entries


def parse_education(lines: list[str]) -> list[dict]:
    entries = []
    current: dict | None = None

    for line in lines:
        if not line.strip():
            continue
        date_match = DATE_PATTERN.search(line)
        if current is None or (date_match and len(line) < 60):
            if current:
                entries.append(current)
            current = {
                "institution": line.strip() if not date_match else "",
                "degree": "",
                "field_of_study": "",
                "date_range": line.strip() if date_match else "",
                "source": "cv",
            }
        elif not current["institution"]:
            current["institution"] = line.strip()
        elif not current["degree"]:
            current["degree"] = line.strip()
        elif not current["field_of_study"]:
            current["field_of_study"] = line.strip()

    if current:
        entries.append(current)
    return entries


def parse_skills(lines: list[str]) -> list[dict]:
    skills = []
    for line in lines:
        # Split by common delimiters: comma, pipe, bullet, semicolon
        parts = re.split(r"[,|•·;/]+", line)
        for part in parts:
            name = part.strip().strip("–-•·")
            if name and len(name) > 1 and len(name) < 60:
                skills.append({"name": name, "endorsements": None, "source": "cv"})
    return skills


def parse_certifications(lines: list[str]) -> list[dict]:
    entries = []
    for line in lines:
        if not line.strip():
            continue
        date_match = DATE_PATTERN.search(line)
        issued = date_match.group() if date_match else None
        name = DATE_PATTERN.sub("", line).strip().strip("–-")
        if name:
            entries.append({"name": name, "issuer": None, "issued_date": issued, "source": "cv"})
    return entries


def parse_projects(lines: list[str]) -> list[dict]:
    entries = []
    current: dict | None = None
    for line in lines:
        if not line.strip():
            continue
        url_match = re.search(r"https?://\S+", line)
        if current is None or (len(line) < 60 and not url_match):
            if current:
                entries.append(current)
            current = {"name": line.strip(), "description": "", "url": None, "source": "cv"}
        elif url_match:
            if current:
                current["url"] = url_match.group()
        else:
            current["description"] = (current["description"] + " " + line).strip()
    if current:
        entries.append(current)
    return entries


def parse_languages(lines: list[str]) -> list[dict]:
    langs = []
    for line in lines:
        if not line.strip():
            continue
        parts = re.split(r"[:\-–|,]", line, maxsplit=1)
        name = parts[0].strip()
        proficiency = parts[1].strip() if len(parts) > 1 else None
        if name:
            langs.append({"name": name, "proficiency": proficiency})
    return langs


def parse_cv(
    cv_path: str = CV_PDF_PATH,
    output_path: str = OUTPUT_PATH,
) -> dict:
    if not cv_path:
        raise CVParseError(
            "CV_PDF_PATH is not set in .env\n"
            "Set it to the absolute path of your CV PDF."
        )

    log.info("Extracting text from: %s", cv_path)
    full_text = extract_text(cv_path)

    # Save raw text for debugging
    Path(RAW_TEXT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(RAW_TEXT_PATH, "w") as f:
        f.write(full_text)
    log.info("Raw text saved to %s (%d chars)", RAW_TEXT_PATH, len(full_text))

    lines = full_text.split("\n")
    sections = detect_sections(lines)

    contact = parse_contact_from_header(sections.get("header", []))
    if "contact" in sections:
        extra_contact = parse_contact_from_header(sections["contact"])
        for k, v in extra_contact.items():
            if v and not contact.get(k):
                contact[k] = v

    summary_lines = sections.get("summary", [])
    summary = " ".join(l for l in summary_lines if l.strip())

    cv_data = {
        "meta": {
            "parsed_at": datetime.now(timezone.utc).isoformat(),
            "source_file": str(cv_path),
        },
        "identity": {
            "full_name": contact.get("full_name", ""),
            "email": contact.get("email"),
            "location": contact.get("location", ""),
            "summary": summary,
        },
        "experience": parse_experience(sections.get("experience", [])),
        "education": parse_education(sections.get("education", [])),
        "skills": parse_skills(sections.get("skills", [])),
        "certifications": parse_certifications(sections.get("certifications", [])),
        "projects": parse_projects(sections.get("projects", [])),
        "languages": parse_languages(sections.get("languages", [])),
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(cv_data, f, indent=2, ensure_ascii=False)

    log.info(
        "CV data saved to %s — %d experience, %d skills, %d education",
        output_path,
        len(cv_data["experience"]),
        len(cv_data["skills"]),
        len(cv_data["education"]),
    )
    return cv_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cv-path", help="Override CV_PDF_PATH from .env")
    args = parser.parse_args()

    parse_cv(cv_path=args.cv_path or CV_PDF_PATH)
