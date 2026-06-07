# Auto-Apply Architect 🚀

A production-ready job application automation tool with:

- **User Dashboard** — resume upload, skill profile, job preferences
- **Matching Engine** — AI-scored skill comparison against job descriptions
- **Automation Engine** — Playwright + stealth for LinkedIn, Internshala, Unstop
- **Application Tracker** — SQLite database logging every application
- **Background Workers** — threading so the browser runs without blocking the UI
- **Security** — Fernet-encrypted cookie storage, dotenv secrets

--

## Project Structure is shown below

```
auto_apply_tool/
├── app.py                      ← Flask server + job orchestrator
├── .env.example                ← Copy to .env and fill in values
├── requirements.txt
│
├── automation/
│   ├── base_scraper.py         ← Abstract base: delays, stealth, error handling
│   ├── linkedin.py             ← LinkedIn Easy Apply scraper
│   ├── internshala.py          ← Internshala application scraper
│   └── unstop.py               ← Unstop job application scraper
│
├── utils/
│   ├── matcher.py              ← Skill-match scoring engine (0–100)
│   ├── resume_parser.py        ← PDF text extraction + skill detection
│   └── security.py             ← Cookie encryption/decryption (Fernet)
│
├── db/
│   └── tracker.py              ← SQLite application logger (thread-safe)
│
├── templates/
│   └── dashboard.html          ← Full SPA dashboard
│
└── resumes/                    ← Uploaded resume PDFs (git-ignored)
```

---

## Setup

### 1. Prerequisites

- Python 3.10+
- pip

### 2. Install Dependencies

```bash
cd auto_apply_tool
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Install Playwright Browsers

```bash
playwright install chromium
playwright install-deps chromium   # Linux only
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env and set SECRET_KEY and optionally OPENAI_API_KEY
```

### 5. Run the Server

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

---

## How to Use

### Step 1 — Fill Your Profile

Enter your name, phone, role, skills, education, experience, and resume PDF.

### Step 2 — Select Platforms

Check LinkedIn, Internshala, and/or Unstop.

### Step 3 — Add Session Cookies (Recommended)

To avoid needing to log in manually every time:

1. Log in to LinkedIn / Internshala in Chrome
2. Install the **Cookie-Editor** browser extension
3. Click Export → Copy as JSON
4. Paste into the "Session Cookies" field in the dashboard

This is more stable than username/password automation and avoids CAPTCHA challenges.

### Step 4 — Click "Start Auto-Apply"

The tool will:
1. Parse your resume and extract skills
2. Search for matching jobs on each platform
3. Score each job (0–100) against your skills and preferences
4. Apply only to jobs with a score ≥ 40 (configurable in `matcher.py`)
5. Fill forms with human-like delays and submit
6. Log every application to the database

### Step 5 — Monitor Progress

The live log panel updates every 2 seconds. After completion, the Application History table shows all submissions.

---

## Anti-Bot Protections

LinkedIn and other platforms detect bots aggressively. This tool uses:

| Technique | How |
|---|---|
| **playwright-stealth** | Patches navigator properties that expose headless Chrome |
| **Randomised delays** | `human_delay()` sleeps 1.5–4 s between actions; `micro_delay()` between keystrokes |
| **Realistic User-Agent** | Set to a real Chrome/Windows UA string |
| **Cookie auth** | Avoids the login flow that is most heavily fingerprinted |
| **Slow typing** | Characters typed one at a time with random inter-key pauses |

> **⚠️ Important:** Even with these measures, running the bot too frequently or against too many jobs in one session can lead to a temporary account restriction. Apply in batches of 10–20 per day. The `MAX_APPLY_PER_RUN` env var enforces a safety cap.

---

## Skill Matching Engine

`utils/matcher.py` — `SkillMatcher.score(job)` returns **0–100**:

| Component | Weight |
|---|---|
| Role title keyword overlap | 40% |
| Skill overlap with job description | 40% |
| Location preference match | 10% |
| Experience requirement ≤ user's years | 10% |

A job is applied to only if score ≥ `min_score` (default: **40**).

---

## Resume Parsing

`utils/resume_parser.py` uses two methods:

1. **Keyword matching** — regex search across 80+ known tech skills in the extracted PDF text
2. **AI extraction** (optional) — calls GPT-4o-mini if `OPENAI_API_KEY` is set for more nuanced extraction

---

## Database Schema

Applications are stored in `db/applications.db` (SQLite):

```sql
CREATE TABLE applications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company     TEXT,
    role        TEXT,
    platform    TEXT,     -- 'linkedin' | 'internshala' | 'unstop'
    job_url     TEXT,
    status      TEXT,     -- 'Applied' | 'Rejected' | 'Interview' | etc.
    applied_at  TEXT,     -- ISO 8601 datetime
    notes       TEXT      -- e.g. "Match score: 72"
);
```

---

## Adding a New Platform

1. Create `automation/my_platform.py` extending `BaseScraper`
2. Implement `login()`, `search_jobs()`, `apply_to_job()`
3. Register in `app.py`:
   ```python
   SCRAPERS["my_platform"] = MyPlatformScraper
   ```
4. Add a checkbox to `templates/dashboard.html`

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `playwright install` fails | Run with `sudo` on Linux or as admin on Windows |
| Cookie login doesn't work | Log out and re-export cookies; they expire after ~24 h |
| Bot gets detected | Reduce `MAX_APPLY_PER_RUN`, increase delays in `base_scraper.py` |
| PDF text extraction empty | Install `pdfminer.six`: `pip install pdfminer.six` |
| `cryptography` import error | `pip install cryptography` |

---

## Legal & Ethical Disclaimer

This tool automates actions on third-party platforms. Use it only for **your own job applications**, with **your own account**. Review each platform's Terms of Service before using. The authors are not responsible for account restrictions arising from use of this tool.
