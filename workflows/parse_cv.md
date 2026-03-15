# Parse CV

## Objective
Extract structured data from the user's PDF CV using pdfplumber.

## Required Inputs
- `CV_PDF_PATH` in `.env` — absolute path to the PDF file
- PDF must be text-based (not a scanned image)

## Run
```bash
python tools/parse_cv.py
# Or override path:
python tools/parse_cv.py --cv-path /path/to/my_cv.pdf
```

## Output
`.tmp/cv_data.json` containing:
- `identity`: name, email, location, summary
- `experience[]`: title, company, date_range, description
- `education[]`: institution, degree, field_of_study, date_range
- `skills[]`: name (from comma/pipe/bullet-separated skill lists)
- `certifications[]`: name, issued_date
- `projects[]`: name, description, url
- `languages[]`: name, proficiency

`.tmp/cv_raw_text.txt` — raw extracted text for debugging

## How Section Detection Works
The tool scans for lines that match section header patterns (case-insensitive):
- EXPERIENCE / WORK EXPERIENCE / EMPLOYMENT
- EDUCATION / ACADEMIC
- SKILLS / TECHNICAL SKILLS / TECHNOLOGIES
- CERTIFICATIONS / LICENSES / COURSES
- PROJECTS / PORTFOLIO
- LANGUAGES
- SUMMARY / PROFILE / OBJECTIVE

Lines that match these patterns mark the start of a new section. Everything between two headers is parsed as that section's content.

## Known Constraints
- **Image-only PDFs will fail** — the tool raises a clear error with instructions.
- Multi-column layouts may mix text from different columns. If output looks garbled, check `.tmp/cv_raw_text.txt`.
- Uncommon section headers may not be detected. Rename them in your CV or add the pattern to `SECTION_HEADERS` in `parse_cv.py`.
- Date parsing uses regex and may miss unusual date formats.

## Troubleshooting
| Problem | Solution |
|---|---|
| "< 100 chars" error | PDF is scanned/image-only. Export as text-based PDF. |
| Skills list is empty | Section header not detected. Check `.tmp/cv_raw_text.txt` for actual header text. |
| Experience entries wrong | Add your actual header text pattern to `SECTION_HEADERS` dict |
| Name is wrong | First non-empty line in the PDF is used as name. Ensure your name is the first line. |
