"""The recruiter agent: a small planner/executor loop around the tools.

Loop:   ready tools = tools whose prerequisites are done
        -> (if several are ready) ask Sarvam which to run first
        -> run it, log the step, repeat   until request_approval or a halt.

Why this is safe: the LLM may only choose from `ready` tools, the dependency graph
is enforced in code, and the Excel file is NOT a tool here - it is created by the
approve endpoint, so no model decision can bypass human approval."""
import json
from datetime import datetime, timezone

from ..config import settings
from ..database import SessionLocal
from ..llm.sarvam import extract_json, llm
from ..models import Screening
from .tools import TOOLS, Ctx


def _log(ctx: Ctx, tool: str, reason: str, observation: str):
    s = ctx.screening
    s.trace = [*s.trace, {"step": len(s.trace) + 1, "tool": tool, "reason": reason,
                          "observation": observation, "at": datetime.now(timezone.utc).isoformat()}]
    ctx.db.commit()  # commit per step so the UI can show live progress


def _choose(ctx: Ctx, ready: list[str], done: set[str]) -> tuple[str, str]:
    if len(ready) == 1 or not settings.agent_use_llm_planner:
        return ready[0], "Next step in the pipeline."
    menu = "\n".join(f"- {t}: {TOOLS[t][2]}" for t in ready)
    prompt = (f"You are a recruiting agent. HR request: {ctx.screening.hr_request[:500]}\n"
              f"Completed steps: {sorted(done) or 'none'}\nTools you may run now:\n{menu}\n"
              'Reply ONLY with JSON: {"tool": "<name>", "reason": "<short reason>"}')
    try:
        data = extract_json(llm.chat([{"role": "user", "content": prompt}], max_tokens=1500, json_mode=True))
        if data.get("tool") in ready:
            return data["tool"], str(data.get("reason", ""))[:200]
    except Exception:
        pass  # planner failure must never break the run
    return ready[0], "Planner unavailable - using default order."


def run_screening(screening_id: int, candidate_ids: list[int] | None = None) -> None:
    """Background job started by POST /api/agent/screen."""
    db = SessionLocal()
    try:
        screening = db.get(Screening, screening_id)
        ctx, done = Ctx(db=db, screening=screening, candidate_ids=candidate_ids), set()
        while True:
            ready = [t for t, (_, req, _) in TOOLS.items() if t not in done and req <= done]
            if not ready:
                break
            tool, reason = _choose(ctx, ready, done)
            observation, halt = TOOLS[tool][0](ctx)
            done.add(tool)
            _log(ctx, tool, reason, observation)
            if halt:
                screening.status, screening.summary = "needs_input", halt
                db.commit()
                return
        db.commit()
    except Exception as e:
        db.rollback()
        s = db.get(Screening, screening_id)
        s.status, s.error = "failed", str(e)[:800]
        db.commit()
    finally:
        db.close()


ANSWER_SYSTEM = """You answer an HR manager's questions about a candidate screening.
Use ONLY the JSON data provided. Quote evidence from it when explaining decisions.
If the data does not contain the answer, say so. Be concise."""


def answer_question(screening: Screening, question: str) -> str:
    rows = [{"rank": r.rank, "name": r.candidate.name or r.candidate.filename, "score": r.score,
             "shortlisted": r.shortlisted, "years": r.experience_years,
             "checks": [{"req": c["requirement"], "met": c["met"], "value": c["candidate_value"],
                         "evidence": (c["evidence"] or "")[:120]} for c in r.checks]}
            for r in screening.results]
    data = json.dumps({"requirements": screening.requirements, "candidates": rows}, ensure_ascii=False)
    return llm.chat([{"role": "system", "content": ANSWER_SYSTEM},
                     {"role": "user", "content": f"DATA:\n{data}\n\nQUESTION: {question}"}])
