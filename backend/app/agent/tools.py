"""The agent's tools. Each tool is a small, single-purpose function that:
  * reads/writes the shared `Ctx` (the agent's working memory),
  * returns (observation, halt_message). A non-empty halt_message means "stop and
    ask the human" (e.g. the JD had no usable criteria).

Keeping tools tiny and typed is what lets the LLM planner pick between them
safely - it can only choose names from the registry, never run arbitrary code."""
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Candidate, Screening, ScreeningResult
from ..services.jd_parser import parse_requirements
from ..services.matcher import rank_and_shortlist, score_candidate


@dataclass
class Ctx:
    db: Session
    screening: Screening
    candidate_ids: list[int] | None = None
    requirements: dict | None = None
    candidates: list = field(default_factory=list)
    scored: list = field(default_factory=list)


def parse_jd(ctx: Ctx):
    req = parse_requirements(ctx.screening.hr_request, ctx.screening.jd_text)
    ctx.requirements = req.model_dump()
    ctx.screening.requirements = ctx.requirements
    ctx.screening.title = req.role_title or "Untitled role"
    obs = (f"Role '{req.role_title}'. Must-have: {', '.join(req.must_have_skills) or 'none'}. "
           f"Nice-to-have: {', '.join(req.nice_to_have_skills) or 'none'}. "
           f"Min experience: {req.min_experience_years or 'not specified'}.")
    if not req.must_have_skills and not req.min_experience_years:
        return obs, ("I couldn't find any concrete criteria (skills or years of experience). "
                     "Please paste the JD or list the required skills and I'll run it again.")
    return obs, None


def retrieve_candidates(ctx: Ctx):
    q = select(Candidate).where(Candidate.parse_status.in_(["parsed", "failed"]))
    if ctx.candidate_ids:
        q = q.where(Candidate.id.in_(ctx.candidate_ids))
    ctx.candidates = list(ctx.db.scalars(q.order_by(Candidate.id)))
    pending = ctx.db.query(Candidate).filter(Candidate.parse_status == "pending").count()
    failed = sum(c.parse_status == "failed" for c in ctx.candidates)
    obs = (f"Loaded {len(ctx.candidates)} candidates from PostgreSQL"
           + (f" ({failed} could not be fully parsed; matched on raw text only)" if failed else "")
           + (f". {pending} resumes are still being parsed and were skipped." if pending else "."))
    return obs, (None if ctx.candidates else "There are no parsed resumes yet. Upload resumes first, then try again.")


def match_candidates(ctx: Ctx):
    ctx.scored = [score_candidate(c, ctx.requirements) for c in ctx.candidates]
    qualified = sum(r["meets_all_required"] for r in ctx.scored)
    return f"Compared {len(ctx.scored)} candidates; {qualified} meet every required criterion.", None


def rank_shortlist(ctx: Ctx):
    ctx.scored = rank_and_shortlist(ctx.scored, ctx.requirements.get("shortlist_limit"))
    n = sum(r["shortlisted"] for r in ctx.scored)
    return f"Ranked candidates and proposed a shortlist of {n}.", None


def save_results(ctx: Ctx):
    s = ctx.screening
    s.results.clear()
    for r in ctx.scored:
        s.results.append(ScreeningResult(
            candidate_id=r["candidate_id"], rank=r["rank"], score=r["score"],
            meets_all_required=r["meets_all_required"], shortlisted=r["shortlisted"],
            experience_years=r["experience_years"], checks=r["checks"]))
    ctx.db.flush()
    return f"Saved {len(ctx.scored)} scored results with evidence to the database.", None


def request_approval(ctx: Ctx):
    s = ctx.screening
    n, total = sum(r["shortlisted"] for r in ctx.scored), len(ctx.scored)
    top = [r for r in ctx.scored if r["shortlisted"]][:3]
    names = {c.id: (c.name or c.filename) for c in ctx.candidates}
    s.summary = (f"Analysed {total} candidates for {s.title}. {n} meet all required criteria."
                 + (" Top matches: " + ", ".join(f"{names[r['candidate_id']]} ({r['score']:g})" for r in top) + "." if top else "")
                 + " Please review the evidence and approve to generate the Excel file.")
    s.status = "awaiting_approval"
    return "Shortlist ready - waiting for human approval before creating the Excel file.", None


# name -> (function, prerequisite tools, description shown to the planner LLM)
TOOLS = {
    "parse_jd": (parse_jd, set(), "Parse the HR request + JD into structured requirements."),
    "retrieve_candidates": (retrieve_candidates, set(), "Load parsed candidate resumes from PostgreSQL."),
    "match_candidates": (match_candidates, {"parse_jd", "retrieve_candidates"}, "Compare every candidate with the requirements and collect evidence."),
    "rank_shortlist": (rank_shortlist, {"match_candidates"}, "Rank candidates and propose a shortlist."),
    "save_results": (save_results, {"rank_shortlist"}, "Persist scores and evidence."),
    "request_approval": (request_approval, {"save_results"}, "Pause and ask the human to approve the shortlist."),
}
