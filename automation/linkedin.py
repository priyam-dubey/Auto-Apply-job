"""
automation/linkedin.py — LinkedIn Easy Apply Scraper

Strategy:
  1. Load cookies if available; else open browser for manual login
  2. Navigate to Jobs, search by role + location
  3. Apply "Easy Apply" filter
  4. For each matching job: open → match → fill multi-step form → submit
"""

from __future__ import annotations

import time

from automation.base_scraper import BaseScraper, human_delay, type_like_human


class LinkedInScraper(BaseScraper):

    PLATFORM = "linkedin"
    BASE_URL = "https://www.linkedin.com"

    # ──────────────────────────────────────────────
    def login(self) -> bool:
        self.page.goto(f"{self.BASE_URL}/login", wait_until="networkidle")
        human_delay(2, 4)

        # Check if already logged in via cookies
        if "/feed" in self.page.url or self.page.query_selector("nav.global-nav"):
            self._log("✅ Already logged in via cookies")
            return True

        # Check for cookie-based login redirect
        self.page.goto(f"{self.BASE_URL}/feed/", wait_until="networkidle")
        human_delay(2, 3)
        if "/feed" in self.page.url:
            self._log("✅ Logged in via cookies")
            return True

        # Fallback: headful manual login
        if self.headless:
            self._log("❌ Cookie login failed and headless=True. Cannot prompt for manual login.")
            return False

        print("\n🔐 Please log in to LinkedIn in the browser window, then press ENTER here …")
        input()
        return "feed" in self.page.url or bool(self.page.query_selector("nav.global-nav"))

    # ──────────────────────────────────────────────
    def search_jobs(self) -> list[dict]:
        role = self.user_data.get("role", "")
        location = self.user_data.get("location", "")

        search_url = (
            f"{self.BASE_URL}/jobs/search/"
            f"?keywords={role.replace(' ', '%20')}"
            f"&location={location.replace(' ', '%20')}"
            f"&f_LF=f_AL"          # Easy Apply filter
        )
        self.page.goto(search_url, wait_until="networkidle")
        human_delay(3, 5)

        jobs: list[dict] = []

        for page_num in range(1, 4):  # Scrape up to 3 pages
            self._log(f"Scraping results page {page_num} …")
            cards = self.page.query_selector_all("ul.jobs-search-results__list > li")

            for card in cards:
                try:
                    title_el = card.query_selector("span[aria-hidden='true']")
                    company_el = card.query_selector("span.job-card-container__primary-description")
                    location_el = card.query_selector("li.job-card-container__metadata-item")
                    link_el = card.query_selector("a.job-card-list__title")

                    if not title_el or not link_el:
                        continue

                    href = link_el.get_attribute("href") or ""
                    job_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

                    jobs.append({
                        "title": title_el.inner_text().strip(),
                        "company": company_el.inner_text().strip() if company_el else "Unknown",
                        "location": location_el.inner_text().strip() if location_el else "",
                        "url": job_url,
                        "description": "",       # fetched lazily in apply_to_job
                        "experience_required": 0,
                    })
                except Exception as exc:
                    self._log(f"⚠️  Error parsing card: {exc}")

            # Go to next page
            next_btn = self.page.query_selector("button[aria-label='View next page']")
            if next_btn and next_btn.is_enabled():
                next_btn.click()
                human_delay(3, 6)
            else:
                break

        self._log(f"Total jobs found: {len(jobs)}")
        return jobs

    # ──────────────────────────────────────────────
    def apply_to_job(self, job: dict) -> bool:
        """Navigate to job page, fetch description, fill Easy Apply form."""
        self.page.goto(job["url"], wait_until="networkidle")
        human_delay(2, 4)

        # Grab job description for matching
        try:
            desc_el = self.page.query_selector("div.jobs-description-content__text")
            job["description"] = desc_el.inner_text() if desc_el else ""
        except Exception:
            job["description"] = ""

        # Click Easy Apply button
        easy_apply_btn = self.page.query_selector("button.jobs-apply-button--top-card")
        if not easy_apply_btn:
            self._log(f"No Easy Apply button for {job.get('title')}")
            return False

        easy_apply_btn.click()
        human_delay(1.5, 3)

        # Fill multi-step form
        return self._fill_easy_apply_form()

    # ──────────────────────────────────────────────
    def _fill_easy_apply_form(self) -> bool:
        """Navigate through the multi-step Easy Apply modal and submit."""
        max_steps = 10  # Safety limit

        for step in range(max_steps):
            self._log(f"Easy Apply step {step + 1}")
            human_delay(1, 2)

            # Check for submit / review button
            submit_btn = self.page.query_selector("button[aria-label='Submit application']")
            if submit_btn:
                submit_btn.click()
                human_delay(2, 3)
                self._log("📨 Application submitted!")
                return True

            # Fill visible text inputs
            inputs = self.page.query_selector_all("input[type='text'], input[type='number'], textarea")
            for inp in inputs:
                try:
                    label = self._get_label_for(inp)
                    placeholder = inp.get_attribute("placeholder") or ""
                    hint = (label or placeholder).lower()

                    if any(k in hint for k in ["phone", "mobile", "contact"]):
                        value = self.user_data.get("phone", "")
                    elif any(k in hint for k in ["city", "location"]):
                        value = self.user_data.get("location", "")
                    elif any(k in hint for k in ["experience", "years"]):
                        value = str(self.user_data.get("experience_years", "0"))
                    elif any(k in hint for k in ["salary", "expected", "ctc"]):
                        value = self.user_data.get("salary", "")
                    elif any(k in hint for k in ["linkedin"]):
                        value = self.user_data.get("linkedin_url", "")
                    elif any(k in hint for k in ["github", "portfolio"]):
                        value = self.user_data.get("portfolio_url", "")
                    else:
                        self._log(f"⚠️  Unknown field [{label or placeholder}] — left blank")
                        continue

                    if value:
                        inp.fill("")
                        type_like_human(inp, value)
                except Exception as exc:
                    self._log(f"⚠️  Field error: {exc}")

            # Handle dropdowns (select elements)
            selects = self.page.query_selector_all("select")
            for sel in selects:
                try:
                    options = sel.query_selector_all("option")
                    if options and len(options) > 1:
                        sel.select_option(index=1)
                except Exception as exc:
                    self._log(f"⚠️  Dropdown error: {exc}")

            # Click "Next" or "Continue" button
            next_btn = (
                self.page.query_selector("button[aria-label='Continue to next step']")
                or self.page.query_selector("button[aria-label='Review your application']")
                or self.page.query_selector("button:has-text('Next')")
                or self.page.query_selector("button:has-text('Continue')")
            )

            if next_btn:
                next_btn.click()
                human_delay(1.5, 3)
            else:
                self._log("⚠️  No Next/Submit button found — stopping form fill")
                break

        self._log("⚠️  Exceeded max form steps")
        return False

    def _get_label_for(self, element) -> str:
        """Try to find the <label> text associated with an input element."""
        try:
            elem_id = element.get_attribute("id") or ""
            if elem_id:
                label_el = self.page.query_selector(f"label[for='{elem_id}']")
                if label_el:
                    return label_el.inner_text().strip()
        except Exception:
            pass
        return ""
