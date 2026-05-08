"""
utils/resume_parser.py

Extracts skills from a PDF resume using:
1. pdfminer/pypdf for text extraction
2. Keyword matching against a curated skill list
3. Optionally calls an AI (OpenAI/Claude) if API key is set.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# ──────────────────────────────────────────────────────────
# Common tech skills to search for
# ──────────────────────────────────────────────────────────
KNOWN_SKILLS: list[str] = [
    # Languages
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "R", "Scala", "Dart", "SQL",
    # Frontend
    "React", "Next.js", "Vue.js", "Angular", "HTML", "HTML5", "CSS", "CSS3",
    "Tailwind", "Bootstrap", "Redux", "GraphQL", "REST API",
    # Backend
    "Node.js", "Django", "Flask", "FastAPI", "Spring Boot", "Express",
    "Laravel", "Rails", "Gin", "Fiber",
    # Databases
    "PostgreSQL", "MySQL", "MongoDB", "SQLite", "Redis", "Elasticsearch",
    "Cassandra", "DynamoDB", "Firebase",
    # DevOps / Cloud
    "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Terraform", "CI/CD",
    "GitHub Actions", "Jenkins", "Ansible", "Linux", "Nginx",
    # ML/AI
    "TensorFlow", "PyTorch", "scikit-learn", "Pandas", "NumPy", "OpenCV",
    "Keras", "Hugging Face", "LangChain", "NLP", "Machine Learning",
    # Tools
    "Git", "Jira", "Figma", "Postman", "Selenium", "Playwright",
    # Soft skills (broad match)
    "communication", "leadership", "problem solving", "teamwork",
]

_SKILL_PATTERNS = [re.compile(r"\b" + re.escape(s) + r"\b", re.IGNORECASE) for s in KNOWN_SKILLS]


# ──────────────────────────────────────────────────────────
def _extract_text_pypdf(pdf_path: str) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
    except Exception:
        return ""


def _extract_text_pdfminer(pdf_path: str) -> str:
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        return pdfminer_extract(pdf_path) or ""
    except Exception:
        return ""


def _extract_text(pdf_path: str) -> str:
    """Try multiple PDF libraries; return whichever gives the most text."""
    texts = [
        _extract_text_pypdf(pdf_path),
        _extract_text_pdfminer(pdf_path),
    ]
    return max(texts, key=len)


# ──────────────────────────────────────────────────────────
def _match_skills_from_text(text: str) -> list[str]:
    found: list[str] = []
    for skill, pattern in zip(KNOWN_SKILLS, _SKILL_PATTERNS):
        if pattern.search(text):
            if skill not in found:
                found.append(skill)
    return found


# ──────────────────────────────────────────────────────────
def _ai_extract_skills(text: str) -> list[str]:
    """
    Optional: call OpenAI (or Anthropic) to extract skills from resume text.
    Reads OPENAI_API_KEY env var. Falls back silently if not set.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or not text.strip():
        return []

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a resume parser. Extract all technical and professional skills "
                        "from the resume text. Return ONLY a comma-separated list of skills, nothing else."
                    ),
                },
                {"role": "user", "content": text[:4000]},
            ],
            max_tokens=200,
            temperature=0,
        )
        raw = resp.choices[0].message.content or ""
        return [s.strip() for s in raw.split(",") if s.strip()]
    except Exception:
        return []


# ──────────────────────────────────────────────────────────
def parse_resume(pdf_path: str) -> list[str]:
    """
    Main entry point.  Returns a deduplicated list of skills found in the PDF.
    """
    if not pdf_path or not Path(pdf_path).exists():
        return []

    text = _extract_text(pdf_path)
    if not text:
        return []

    keyword_skills = _match_skills_from_text(text)
    ai_skills = _ai_extract_skills(text)

    # Merge and deduplicate (case-insensitive)
    seen: set[str] = set()
    merged: list[str] = []
    for skill in keyword_skills + ai_skills:
        key = skill.lower()
        if key not in seen:
            seen.add(key)
            merged.append(skill)

    return merged
