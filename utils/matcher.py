"""
utils/matcher.py — Matching Engine

Compares user's parsed skills + preferences against a scraped job listing.
Returns a match score (0–100) and a boolean "should apply" decision.
"""

from __future__ import annotations

import re


class SkillMatcher:
    """
    Decides whether to apply for a job based on:
    - Skill overlap between user's resume and job description
    - Salary range preference
    - Location preference
    - Role keyword match
    - Experience requirements
    """

    STOP_WORDS = {"and", "or", "the", "a", "an", "with", "in", "of", "for"}

    def __init__(
        self,
        user_skills: list[str],
        user_prefs: dict,
        min_score: int = 40,
    ):
        """
        Parameters
        ----------
        user_skills : list of skills parsed from resume
        user_prefs  : dict with keys like role, skills, salary, location, experience_years
        min_score   : minimum match percentage to trigger application
        """
        self.user_skills = {s.lower() for s in user_skills}
        # Also include manually entered skills from form
        for skill in user_prefs.get("skills", []):
            self.user_skills.add(skill.lower())

        self.preferred_role = user_prefs.get("role", "").lower()
        self.preferred_location = user_prefs.get("location", "").lower()
        self.preferred_salary = user_prefs.get("salary", "")
        self.max_experience = int(user_prefs.get("experience_years", 99))
        self.min_score = min_score

    # ──────────────────────────────────
    def score(self, job: dict) -> int:
        """
        Returns 0–100 match score for a job dict containing:
          title, description, company, location, salary (optional), experience (optional)
        """
        total_weight = 0
        earned = 0

        title: str = job.get("title", "").lower()
        description: str = job.get("description", "").lower()
        location: str = job.get("location", "").lower()
        salary_str: str = str(job.get("salary", "")).lower()
        req_exp: int = int(job.get("experience_required", 0) or 0)

        # ── 1. Role title match (40 pts) ──────────────────
        total_weight += 40
        if self.preferred_role:
            role_words = set(self.preferred_role.split()) - self.STOP_WORDS
            title_words = set(title.split())
            overlap = role_words & title_words
            role_score = (len(overlap) / len(role_words)) * 40 if role_words else 0
            earned += min(role_score, 40)

        # ── 2. Skill overlap with description (40 pts) ────
        total_weight += 40
        if self.user_skills:
            jd_text = f"{title} {description}"
            matched_skills = sum(
                1 for skill in self.user_skills
                if re.search(r"\b" + re.escape(skill) + r"\b", jd_text, re.IGNORECASE)
            )
            skill_score = min((matched_skills / len(self.user_skills)) * 40, 40)
            earned += skill_score

        # ── 3. Location match (10 pts) ────────────────────
        total_weight += 10
        if not self.preferred_location or self.preferred_location in ("any", "remote", ""):
            earned += 10  # no preference = always match
        elif self.preferred_location in location or "remote" in location:
            earned += 10

        # ── 4. Experience requirements (10 pts) ───────────
        total_weight += 10
        if req_exp <= self.max_experience:
            earned += 10

        return int((earned / total_weight) * 100) if total_weight else 0

    def should_apply(self, job: dict) -> tuple[bool, int]:
        """Returns (should_apply: bool, score: int)."""
        s = self.score(job)
        return s >= self.min_score, s

    # ──────────────────────────────────
    def explain(self, job: dict) -> str:
        """Human-readable explanation of the match decision."""
        apply, s = self.should_apply(job)
        decision = "✅ APPLY" if apply else "⛔ SKIP"
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        return f"{decision} — {company} | {title} | Score: {s}/100"
