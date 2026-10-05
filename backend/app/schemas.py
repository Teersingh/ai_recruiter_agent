"""Pydantic models: (1) validate what the LLM returns for the JD, (2) validate
request bodies, (3) turn ORM rows into JSON for the frontend."""
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Requirements(BaseModel):
    """Structured form of a job description. The matcher only ever reads this."""
    role_title: str = ""
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    min_experience_years: Optional[float] = None
    shortlist_limit: Optional[int] = None  # e.g. HR says "top 10"
    notes: str = ""

    @field_validator("must_have_skills", "nice_to_have_skills", mode="before")
    @classmethod
    def _clean_skills(cls, v):
        seen, out = set(), []
        for s in v or []:
            s = str(s).strip()
            if s and s.lower() not in seen:
                seen.add(s.lower())
                out.append(s)
        return out

    @field_validator("min_experience_years", "shortlist_limit", mode="before")
    @classmethod
    def _nullable_number(cls, v):
        try:
            return None if v in (None, "", 0) else float(v)
        except (TypeError, ValueError):
            return None

    @field_validator("shortlist_limit")
    @classmethod
    def _int_limit(cls, v):
        return int(v) if v else None


class AskIn(BaseModel):
    question: str


class OverrideIn(BaseModel):
    shortlisted: bool


# ---------- serializers ----------
def candidate_out(c) -> dict:
    p = c.profile or {}
    return {
        "id": c.id, "filename": c.filename, "name": c.name, "email": c.email, "phone": c.phone,
        "parse_status": c.parse_status, "parse_error": c.parse_error,
        "experience_years": p.get("experience_years"), "skills": p.get("skills", []),
    }


def result_out(r) -> dict:
    return {
        "id": r.id, "candidate_id": r.candidate_id, "name": r.candidate.name or r.candidate.filename,
        "email": r.candidate.email, "phone": r.candidate.phone, "rank": r.rank,
        "score": r.score, "meets_all_required": r.meets_all_required,
        "shortlisted": r.shortlisted, "overridden": r.overridden,
        "experience_years": r.experience_years, "checks": r.checks,
    }


def screening_out(s, with_results: bool = False) -> dict:
    d = {
        "id": s.id, "title": s.title, "hr_request": s.hr_request, "requirements": s.requirements,
        "status": s.status, "trace": s.trace, "summary": s.summary, "error": s.error,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "approved_at": s.approved_at.isoformat() if s.approved_at else None,
        "has_excel": bool(s.excel_path),
    }
    if with_results:
        d["results"] = [result_out(r) for r in s.results]
    return d
