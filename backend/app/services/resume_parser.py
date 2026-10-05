"""Resume -> structured profile.

Division of labour (key anti-hallucination design):
  * The LLM only EXTRACTS facts (name, jobs with dates, education, skills).
  * Our code COMPUTES total experience from the dates (LLMs are bad at date math)
    and merges overlapping jobs so nobody is double-counted.
  * Evidence for skill matches is later searched in the raw text (matcher.py)."""
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from ..config import settings
from ..database import SessionLocal
from ..llm.sarvam import llm
from ..models import Candidate

SYSTEM = """You extract structured data from a resume. Reply with ONLY a JSON object:
{"name": str|null, "email": str|null, "phone": str|null,
 "skills": [str],
 "experience": [{"title": str, "company": str, "start": "YYYY-MM"|"YYYY", "end": "YYYY-MM"|"YYYY"|"present", "description": str}],
 "education": [{"degree": str, "institution": str, "year": str|null}],
 "stated_total_experience_years": number|null}
Rules: copy facts only from the resume, never invent. Use null if unknown. Internships count as experience
entries too. "stated_total_experience_years" is only a number the resume itself states (e.g. "3 years of experience")."""

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{8,}\d)")


def _month_index(value, is_end: bool):
    """'2021-03' -> months since year 0. Year-only start = Jan, year-only end = Dec."""
    if str(value).strip().lower() in ("present", "current", "now", "till date", "ongoing"):
        t = date.today()
        return t.year * 12 + t.month
    m = re.match(r"(\d{4})(?:-(\d{1,2}))?", str(value or "").strip())
    if not m:
        return None
    month = int(m.group(2)) if m.group(2) else (12 if is_end else 1)
    return int(m.group(1)) * 12 + min(max(month, 1), 12)


def compute_experience_years(experience: list[dict]) -> float:
    spans = []
    for e in experience or []:
        s, t = _month_index(e.get("start"), False), _month_index(e.get("end"), True)
        if s is not None and t is not None and t > s:
            spans.append((s, t))
    spans.sort()
    total, cur_s, cur_e = 0, None, None
    for s, t in spans:  # merge overlapping jobs
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, t
        else:
            cur_e = max(cur_e, t)
    if cur_e is not None:
        total += cur_e - cur_s
    return round(total / 12, 1)


def parse_resume_text(text: str) -> dict:
    data = llm.chat_json(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text[:12000]}]
    )
    exp = [e for e in (data.get("experience") or []) if isinstance(e, dict)]
    years = compute_experience_years(exp)
    source = "computed from job dates"
    if years == 0 and data.get("stated_total_experience_years"):
        try:
            years, source = round(float(data["stated_total_experience_years"]), 1), "stated in resume"
        except (TypeError, ValueError):
            pass
    return {
        "name": data.get("name"), "email": data.get("email"), "phone": data.get("phone"),
        "skills": [str(s) for s in (data.get("skills") or [])],
        "experience": exp, "education": data.get("education") or [],
        "experience_years": years, "experience_source": source,
    }


def parse_candidate(candidate_id: int) -> None:
    """Parse one stored resume. Own DB session because this runs in worker threads."""
    db = SessionLocal()
    try:
        c = db.get(Candidate, candidate_id)
        email = EMAIL_RE.search(c.raw_text)
        phone = PHONE_RE.search(c.raw_text)
        c.email = email.group(0) if email else None   # regex first: works even if the LLM fails
        c.phone = phone.group(0).strip() if phone else None
        try:
            p = parse_resume_text(c.raw_text)
            c.profile = p
            c.name = p["name"] or c.name
            c.email, c.phone = p["email"] or c.email, p["phone"] or c.phone
            c.parse_status, c.parse_error = "parsed", None
        except Exception as e:  # keep the resume searchable even if extraction failed
            c.parse_status, c.parse_error = "failed", str(e)[:500]
            c.name = c.name or c.raw_text.strip().split("\n")[0][:80]
        db.commit()
    finally:
        db.close()


def parse_many(candidate_ids: list[int]) -> None:
    with ThreadPoolExecutor(max_workers=settings.parse_workers) as pool:
        list(pool.map(parse_candidate, candidate_ids))
