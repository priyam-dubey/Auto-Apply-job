"""
automation/base_scraper.py

Base class for all platform scrapers.

Key features:
  - Playwright with playwright-stealth for anti-bot evasion
  - Randomised, human-like delays between every action
  - Robust error handling: unknown fields are logged, not raised
  - Session cookie loading/saving
"""

from __future__ import annotations

import random
import time
import traceback
from abc import ABC, abstractmethod

from db.tracker import ApplicationTracker
from utils.matcher import SkillMatcher


# ──────────────────────────────────────────────────────────
# Human-Like Delays
# ──────────────────────────────────────────────────────────

def human_delay(min_s: float = 1.5, max_s: float = 4.0):
    """Sleep for a random duration to mimic human timing."""
    time.sleep(random.uniform(min_s, max_s))


def micro_delay():
    """Very short pause between keystrokes."""
    time.sleep(random.uniform(0.05, 0.18))


def type_like_human(element, text: str):
    """Type text into a Playwright element char-by-char with random delays."""
    for char in text:
        element.type(char)
        micro_delay()


# ──────────────────────────────────────────────────────────
class BaseScraper(ABC):
    """
    Abstract base for LinkedIn, Internshala, Unstop scrapers.

    Subclasses must implement:
      - login()        → bool (True if logged in)
      - search_jobs()  → list[dict]  each dict: title, company, url, description, ...
      - apply_to_job() → bool (True if applied successfully)
    """

    PLATFORM = "base"

    def __init__(
        self,
        user_data: dict,
        matcher: SkillMatcher,
        tracker: ApplicationTracker,
        cookies: str | None = None,
        headless: bool = True,
    ):
        self.user_data = user_data
        self.matcher = matcher
        self.tracker = tracker
        self._cookie_str = cookies
        self.headless = headless
        self.browser = None
        self.page = None
        self._applied_count = 0

    # ──────────────────────────────────
    def _launch_browser(self):
        """Launch Playwright with stealth settings."""
        from playwright.sync_api import sync_playwright
        from playwright_stealth import stealth_sync  # type: ignore

        self._playwright = sync_playwright().start()

        launch_kwargs = {
            "headless": self.headless,
            "args": [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
                "--lang=en-US,en",
            ],
        }

        self.browser = self._playwright.chromium.launch(**launch_kwargs)
        context = self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="Asia/Kolkata",
            viewport={"width": 1366, "height": 768},
        )

        # Load saved cookies if available
        if self._cookie_str:
            self._load_cookies(context)

        self.page = context.new_page()
        stealth_sync(self.page)

    def _load_cookies(self, context):
        """Parse and inject cookie string into browser context."""
        import json as _json

        try:
            cookies = _json.loads(self._cookie_str)
            context.add_cookies(cookies)
        except Exception:
            # Maybe it's a raw Netscape/header format
            pass

    def _close_browser(self):
        if self.browser:
            self.browser.close()
        if hasattr(self, "_playwright"):
            self._playwright.stop()

    # ──────────────────────────────────
    def _safe_fill(self, selector: str, value: str, *, label: str = "field"):
        """Fill a form field; log if not found instead of raising."""
        try:
            el = self.page.wait_for_selector(selector, timeout=5000)
            if el:
                el.fill("")
                type_like_human(el, value)
        except Exception as exc:
            self._log(f"⚠️  Unknown field [{label}] — {exc} — skipped")

    def _safe_click(self, selector: str, *, label: str = "button"):
        """Click an element; log if not found."""
        try:
            el = self.page.wait_for_selector(selector, timeout=5000)
            if el:
                human_delay(0.5, 1.2)
                el.click()
        except Exception as exc:
            self._log(f"⚠️  Cannot click [{label}] — {exc} — skipped")

    def _log(self, message: str):
        print(f"[{self.PLATFORM.upper()}] {message}")

    # ──────────────────────────────────
    @abstractmethod
    def login(self) -> bool:
        """Authenticate (via cookies or manual prompt). Returns True on success."""

    @abstractmethod
    def search_jobs(self) -> list[dict]:
        """Scrape a list of job postings matching user preferences."""

    @abstractmethod
    def apply_to_job(self, job: dict) -> bool:
        """Fill and submit the application for a single job. Returns True on success."""

    # ──────────────────────────────────
    def run(self) -> dict:
        """
        Orchestrate the full flow:
          1. Launch browser
          2. Login
          3. Search jobs
          4. For each job: match → apply → track
        Returns summary dict.
        """
        self._launch_browser()
        result = {"applied": 0, "skipped": 0, "errors": 0}

        try:
            logged_in = self.login()
            if not logged_in:
                self._log("❌ Login failed — aborting")
                result["errors"] += 1
                return result

            jobs = self.search_jobs()
            self._log(f"Found {len(jobs)} jobs to evaluate")

            for job in jobs:
                should_apply, score = self.matcher.should_apply(job)
                self._log(self.matcher.explain(job))

                if not should_apply:
                    result["skipped"] += 1
                    continue

                # Skip duplicates
                if self.tracker.already_applied(
                    job.get("company", ""), job.get("title", ""), self.PLATFORM
                ):
                    self._log(f"⏭️  Already applied to {job.get('company')} — {job.get('title')}")
                    result["skipped"] += 1
                    continue

                try:
                    applied = self.apply_to_job(job)
                    if applied:
                        self.tracker.log(
                            company=job.get("company", "Unknown"),
                            role=job.get("title", "Unknown"),
                            platform=self.PLATFORM,
                            job_url=job.get("url", ""),
                            status="Applied",
                            notes=f"Match score: {score}",
                        )
                        result["applied"] += 1
                        self._log(f"✅ Applied: {job.get('company')} — {job.get('title')}")
                    else:
                        result["errors"] += 1
                except Exception as exc:
                    self._log(f"❌ Error applying: {exc}")
                    self._log(traceback.format_exc())
                    result["errors"] += 1

                human_delay(3, 7)  # Pause between applications

        finally:
            self._close_browser()

        return result
