# Setup LinkedIn Session (One-Time)

## Objective
Create a saved browser session so Playwright can access LinkedIn without storing your email or password.

## When to Run
- **First time** setting up this project
- **When** any Playwright tool fails with "session expired" or redirects to the login page (typically every 30-90 days)

## Prerequisites
- Python and dependencies installed (`pip install playwright && playwright install chromium`)
- `.env` file exists with `LINKEDIN_COOKIES_PATH` set (default: `.tmp/linkedin_cookies.json`)

## Steps

1. **Open a terminal** in the project directory.

2. **Run the setup tool:**
   ```bash
   python tools/save_linkedin_session.py
   ```

3. **A browser window will open.** Log into LinkedIn as you normally would:
   - Enter your email and password
   - Complete any 2FA or security challenges LinkedIn presents
   - Wait until you see your LinkedIn feed (the home page with posts)

4. **Return to the terminal** and press `ENTER` when prompted.

5. **Verify success:**
   - The script prints the number of cookies saved and the file path
   - Check that `.tmp/linkedin_cookies.json` exists and is non-empty

## Expected Output
```
Session saved to: .tmp/linkedin_cookies.json
Cookies count: 23
You can now run the full pipeline.
```

## Troubleshooting

| Problem | Solution |
|---|---|
| Browser opens but immediately closes | Make sure you pressed ENTER only after seeing the feed |
| "No cookies found" error | Log in fully before pressing ENTER |
| LinkedIn shows a verification challenge | Complete it in the browser, then press ENTER |
| Script hangs after pressing ENTER | Close the browser manually if needed; the script will detect cookies |

## Security Note
The cookies file (`.tmp/linkedin_cookies.json`) is listed in `.gitignore` and will never be committed to the repository. It contains your LinkedIn session tokens — treat it like a password file.
