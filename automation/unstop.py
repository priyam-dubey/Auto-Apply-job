"""
automation/unstop.py — Unstop (formerly Dare2Compete) Job Scraper

Strategy:
  1. Cookie-based auth
  2. Search jobs by role keyword
  3. Match → Apply → Fill form → Submit
"""

from __future__ import annotations

from automation.base_scraper import BaseScraper, human_delay, type_like_human


class UnstopScraper(BaseScraper):

    PLATFORM = "unstop"
    BASE_URL = "https://unstop.com"

    # ──────────────────────────────────────────────
    def login(self) -> bool:
        self.page.goto(f"{self.BASE_URL}/dashboard", wait_until="networkidle")
        human_delay(2, 4)

        if "/dashboard" in self.page.url:
            self._log("✅ Logged in via cookies")
            return True

        if self.headless:
            self._log("❌ Not logged in and headless mode — cannot prompt")
            return False

        print("\n🔐 Please log in to Unstop in the browser window, then press ENTER …")
        input()
        self.page.goto(f"{self.BASE_URL}/dashboard", wait_until="networkidle")
        return "/dashboard" in self.page.url

    # ──────────────────────────────────────────────
    def search_jobs(self) -> list[dict]:
        role = self.user_data.get("role", "")
        search_url = f"{self.BASE_URL}/jobs?q={role.replace(' ', '+')}&type=job"
        self.page.goto(search_url, wait_until="networkidle")
        human_delay(2, 4)

        jobs: list[dict] = []

        cards = self.page.query_selector_all(".job-card, .opportunity--wrapper")
        for card in cards:
            try:
                title_el = card.query_selector(".title, h2.truncate")
                company_el = card.query_selector(".company-name, .org-name")
                location_el = card.query_selector(".location, .job-location")
                link_el = card.query_selector("a[href]")

                href = link_el.get_attribute("href") if link_el else ""
                job_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

                jobs.append({
                    "title": title_el.inner_text().strip() if title_el else "Unknown",
                    "company": company_el.inner_text().strip() if company_el else "Unknown",
                    "location": location_el.inner_text().strip() if location_el else "",
                    "url": job_url,
                    "description": "",
                    "experience_required": 0,
                })
            except Exception as exc:
                self._log(f"⚠️  Card parse error: {exc}")

        self._log(f"Found {len(jobs)} jobs on Unstop")
        return jobs

    # ──────────────────────────────────────────────
    def apply_to_job(self, job: dict) -> bool:
        self.page.goto(job["url"], wait_until="networkidle")
        human_delay(2, 4)

        try:
            desc_el = self.page.query_selector(".job-description, .description-section")
            job["description"] = desc_el.inner_text() if desc_el else ""
        except Exception:
            job["description"] = ""

        apply_btn = (
            self.page.query_selector("button:has-text('Apply')")
            or self.page.query_selector("a:has-text('Apply Now')")
        )

        if not apply_btn:
            self._log(f"No Apply button for: {job.get('title')}")
            return False

        apply_btn.click()
        human_delay(2, 4)

        return self._fill_application_form()

    def _fill_application_form(self) -> bool:
        # Fill basic profile fields if shown
        inputs = self.page.query_selector_all("input[type='text'], textarea")
        for inp in inputs:
            try:
                placeholder = (inp.get_attribute("placeholder") or "").lower()
                if "experience" in placeholder or "years" in placeholder:
                    type_like_human(inp, str(self.user_data.get("experience_years", "0")))
                elif "cover" in placeholder or "about" in placeholder:
                    type_like_human(inp, "I am excited about this opportunity and believe my skills are a great fit.")
                human_delay(0.3, 0.8)
            except Exception as exc:
                self._log(f"⚠️  Field error: {exc}")

        submit_btn = (
            self.page.query_selector("button[type='submit']")
            or self.page.query_selector("button:has-text('Submit')")
        )

        if submit_btn:
            human_delay(1, 2)
            submit_btn.click()
            human_delay(2, 4)
            self._log("📨 Unstop application submitted!")
            return True

        self._log("⚠️  No submit button found on Unstop")
        return False
