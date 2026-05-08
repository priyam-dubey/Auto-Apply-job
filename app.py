"""
Auto-Apply Job Tool — Main Flask Application
Handles the web dashboard, resume upload, job preferences,
and dispatches background automation workers per platform.
"""

import json
import os
import threading
import uuid
from datetime import datetime

from flask import Flask, jsonify, render_template, request

from automation.internshala import IntershalaScraper
from automation.linkedin import LinkedInScraper
from automation.unstop import UnstopScraper
from db.tracker import ApplicationTracker
from utils.matcher import SkillMatcher
from utils.resume_parser import parse_resume
from utils.security import decrypt_cookies, encrypt_cookies

# ──────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

UPLOAD_FOLDER = "resumes"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

tracker = ApplicationTracker()

# In-memory job registry: job_id → {status, log, result}
job_registry: dict[str, dict] = {}
job_lock = threading.Lock()


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _new_job_id() -> str:
    return str(uuid.uuid4())


def _update_job(job_id: str, **kwargs):
    with job_lock:
        job_registry[job_id].update(kwargs)


def _append_log(job_id: str, message: str):
    with job_lock:
        job_registry[job_id]["log"].append(
            f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        )


# ──────────────────────────────────────────────
# Background worker
# ──────────────────────────────────────────────

SCRAPERS = {
    "linkedin": LinkedInScraper,
    "internshala": IntershalaScraper,
    "unstop": UnstopScraper,
}


def _run_automation(job_id: str, user_data: dict, platforms: list[str]):
    """Runs in a background thread.  One scraper per platform."""
    _update_job(job_id, status="running")

    # Parse resume skills (AI-assisted)
    resume_path = user_data.get("resume_path", "")
    _append_log(job_id, f"Parsing resume: {resume_path}")
    parsed_skills = parse_resume(resume_path)
    _append_log(job_id, f"Detected skills: {', '.join(parsed_skills)}")

    matcher = SkillMatcher(user_skills=parsed_skills, user_prefs=user_data)

    for platform in platforms:
        ScraperClass = SCRAPERS.get(platform)
        if not ScraperClass:
            _append_log(job_id, f"⚠️  Unknown platform: {platform} — skipped")
            continue

        _append_log(job_id, f"▶  Starting {platform} automation …")

        # Load saved cookies for this platform (if any)
        cookies_enc = user_data.get(f"{platform}_cookies", "")
        cookies = decrypt_cookies(cookies_enc) if cookies_enc else None

        scraper = ScraperClass(
            user_data=user_data,
            matcher=matcher,
            tracker=tracker,
            cookies=cookies,
        )

        try:
            result = scraper.run()
            _append_log(job_id, f"✅ {platform}: {result.get('applied', 0)} applications submitted")
        except Exception as exc:
            _append_log(job_id, f"❌ {platform} failed: {exc}")

    _update_job(job_id, status="done")
    _append_log(job_id, "All platforms finished.")


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/submit", methods=["POST"])
def submit():
    """Accept form data + resume, kick off background worker."""
    role = request.form.get("role", "").strip()
    skills_raw = request.form.get("skills", "")
    salary = request.form.get("salary", "")
    location = request.form.get("location", "")
    experience = request.form.get("experience", "0")
    education = request.form.get("education", "")
    platforms = request.form.getlist("platforms")

    # LinkedIn cookies (optional, pasted by user)
    linkedin_cookies_raw = request.form.get("linkedin_cookies", "")
    internshala_cookies_raw = request.form.get("internshala_cookies", "")

    if not role or not platforms:
        return jsonify({"error": "Role and at least one platform are required."}), 400

    # Save resume
    resume_file = request.files.get("resume")
    resume_path = ""
    if resume_file and resume_file.filename:
        safe_name = f"{uuid.uuid4()}_{resume_file.filename}"
        resume_path = os.path.join(UPLOAD_FOLDER, safe_name)
        resume_file.save(resume_path)

    user_data = {
        "role": role,
        "skills": [s.strip() for s in skills_raw.split(",") if s.strip()],
        "salary": salary,
        "location": location,
        "experience_years": int(experience) if experience.isdigit() else 0,
        "education": education,
        "resume_path": resume_path,
        "platforms": platforms,
        "linkedin_cookies": encrypt_cookies(linkedin_cookies_raw) if linkedin_cookies_raw else "",
        "internshala_cookies": encrypt_cookies(internshala_cookies_raw) if internshala_cookies_raw else "",
    }

    # Persist user profile
    with open("user_data.json", "w") as fh:
        json.dump(user_data, fh, indent=4)

    # Create job
    job_id = _new_job_id()
    with job_lock:
        job_registry[job_id] = {
            "status": "queued",
            "log": [],
            "started_at": datetime.now().isoformat(),
        }

    # Dispatch background thread
    t = threading.Thread(
        target=_run_automation,
        args=(job_id, user_data, platforms),
        daemon=True,
    )
    t.start()

    return jsonify({"job_id": job_id, "message": "Automation started in background."})


@app.route("/api/job/<job_id>")
def job_status(job_id: str):
    """Poll endpoint for frontend progress display."""
    with job_lock:
        job = job_registry.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/applications")
def list_applications():
    """Return all tracked applications from DB."""
    apps = tracker.get_all()
    return jsonify(apps)


@app.route("/api/applications/<int:app_id>", methods=["PATCH"])
def update_application(app_id: int):
    """Manually update status of an application."""
    data = request.get_json(force=True)
    new_status = data.get("status")
    if not new_status:
        return jsonify({"error": "status required"}), 400
    tracker.update_status(app_id, new_status)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
