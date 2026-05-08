"""
automation/internshala.py — Internshala Apply Scraper

Strategy:
  1. Load session cookies (from user paste or manual login)
  2. Search for internships/jobs matching the user's role + location
  3. For each matching posting: open → match → click Apply → fill form → submit
"""

from __future__ import annotations

from automation.base_scraper import BaseScraper, human_delay, type_like_human


class IntershalaScraper(BaseScraper):

    PLATFORM = "internshala"
    BASE_URL = "https://internshala.com"

    # ──────────────────────────────────────────────
    def login(self) -> bool:
        self.page.goto(f"{self.BASE_URL}/student/dashboard", wait_until="networkidle")
        human_delay(2, 4)

        # Cookie-based auth check
        if "/student/dashboard" in self.page.url:
            self._log("✅ Logged in via cookies")
            return True

        if self.headless:
            self._log("❌ Not logged in and headless mode — cannot prompt")
            return False

        print("\n🔐 Please log in to Internshala in the browser window, then press ENTER …")
        input()
        self.page.goto(f"{self.BASE_URL}/student/dashboard", wait_until="networkidle")
        return "/student/dashboard" in self.page.url

    # ──────────────────────────────────────────────
    def search_jobs(self) -> list[dict]:
        role = self.user_data.get("role", "").replace(" ", "-").lower()
        location = self.user_data.get("location", "").replace(" ", "-").lower()

        # Internshala URL pattern for internships
        if location:
            search_url = (
                f"{self.BASE_URL}/internships/{role}-internship-in-{location}/"
            )
        else:
            search_url = f"{self.BASE_URL}/internships/{role}-internship/"

        self.page.goto(search_url, wait_until="networkidle")
        human_delay(2, 4)

        jobs: list[dict] = []
        cards = self.page.query_selector_all(".internship_meta")

        for card in cards:
            try:
                title_el = card.query_selector("h3.job-internship-name a, h3.heading_4_5 a")
                company_el = card.query_selector("p.company-name")
                location_el = card.query_selector("p.location_link, p.locations span")
                link_el = card.query_selector("h3 a, a.view_detail_button")
                stipend_el = card.query_selector("span.stipend, p.stipend")

                href = link_el.get_attribute("href") if link_el else ""
                job_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

                jobs.append({
                    "title": title_el.inner_text().strip() if title_el else "Unknown",
                    "company": company_el.inner_text().strip() if company_el else "Unknown",
                    "location": location_el.inner_text().strip() if location_el else "",
                    "url": job_url,
                    "salary": stipend_el.inner_text().strip() if stipend_el else "",
                    "description": "",
                    "experience_required": 0,
                })
            except Exception as exc:
                self._log(f"⚠️  Card parse error: {exc}")

        self._log(f"Found {len(jobs)} internships")
        return jobs

    # ──────────────────────────────────────────────
    def apply_to_job(self, job: dict) -> bool:
        self.page.goto(job["url"], wait_until="networkidle")
        human_delay(2, 4)

        # Fetch description
        try:
            desc_el = self.page.query_selector("#about_the_internship, .internship_other_details")
            job["description"] = desc_el.inner_text() if desc_el else ""
        except Exception:
            job["description"] = ""

        # Click Apply button
        apply_btn = (
            self.page.query_selector("button#apply-button")
            or self.page.query_selector("a.btn.apply_now_btn")
            or self.page.query_selector("button:has-text('Apply Now')")
        )

        if not apply_btn:
            self._log(f"No Apply button for: {job.get('title')}")
            return False

        apply_btn.click()
        human_delay(2, 4)

        return self._fill_application_form(job)

    # ──────────────────────────────────────────────
    def _fill_application_form(self, job: dict) -> bool:
        """Fill Internshala's application form (cover letter + questions)."""
        # Cover letter textarea
        try:
            cover = self.page.query_selector("textarea#cover_letter, textarea[name='cover_letter']")
            if cover:
                cover_text = self._generate_cover_letter(job)
                type_like_human(cover, cover_text)
                human_delay(1, 2)
        except Exception as exc:
            self._log(f"⚠️  Cover letter field error: {exc}")

        # Custom screening questions
        questions = self.page.query_selector_all(".assessment_question textarea, .screening-question textarea")
        for q_el in questions:
            try:
                q_text = ""
                label = q_el.query_selector("xpath=preceding-sibling::label")
                if label:
                    q_text = label.inner_text().lower()

                if any(k in q_text for k in ["experience", "years"]):
                    answer = str(self.user_data.get("experience_years", "0"))
                elif any(k in q_text for k in ["notice", "join"]):
                    answer = "Immediately"
                else:
                    answer = "As per your requirements, I am happy to contribute."

                type_like_human(q_el, answer)
                human_delay(0.5, 1.5)
            except Exception as exc:
                self._log(f"⚠️  Question field error: {exc}")

        # Submit
        submit_btn = (
            self.page.query_selector("button[type='submit']")
            or self.page.query_selector("button:has-text('Submit')")
            or self.page.query_selector("input[type='submit']")
        )

        if submit_btn:
            human_delay(1, 2)
            submit_btn.click()
            human_delay(2, 4)
            self._log("📨 Internshala application submitted!")
            return True

        self._log("⚠️  No submit button found")
        return False

    def _generate_cover_letter(self, job: dict) -> str:
        role = job.get("title", self.user_data.get("role", "the role"))
        company = job.get("company", "your company")
        skills = ", ".join(self.user_data.get("skills", [])[:5])
        name = self.user_data.get("name", "")
        salutation = f"Dear {company} Team," if company != "Unknown" else "Dear Hiring Team,"

        return (
            f"{salutation}\n\n"
            f"I am excited to apply for the {role} position at {company}. "
            f"With my proficiency in {skills}, I am confident I can add value to your team. "
            f"I am a quick learner, highly motivated, and eager to contribute to real-world projects.\n\n"
            f"I look forward to the opportunity to discuss my application further.\n\n"
            f"Thank you for your time and consideration.\n\n"
            f"Best regards,\n{name}"
        )
