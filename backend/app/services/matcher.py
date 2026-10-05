"""The matching engine: candidate profile + raw text + Requirements -> score + evidence.

100% deterministic (no LLM call), so results are reproducible and auditable.
Every check carries the verbatim resume line that justifies it."""
import re

USAGE_MIN_WORDS = 6  # a line this long describes work done; a short line is just a skill list
W_MUST, W_EXP, W_NICE = 60, 25, 15

from .skills import skill_pattern


def _lines(text: str):
    for raw in text.splitlines():
        line = re.sub(r"^[\s•\-*·▪●]+", "", raw).strip()
        if line:
            yield line


def find_evidence(text: str, skill: str):
    """Return {'quote', 'type'} for the best line mentioning `skill`, else None.
    Prefers a 'usage' line (describes real work) over a bare 'listed' skill."""
    pat, listed = skill_pattern(skill), None
    for line in _lines(text):
        if pat.search(line):
            if len(line.split()) >= USAGE_MIN_WORDS:
                return {"quote": line[:240], "type": "usage"}
            listed = listed or {"quote": line[:240], "type": "listed"}
    return listed


def _fmt_years(v) -> str:
    return f"{v:g}"


def score_candidate(candidate, req: dict) -> dict:
    profile, text = candidate.profile or {}, candidate.raw_text
    must, nice = req.get("must_have_skills", []), req.get("nice_to_have_skills", [])
    min_exp = req.get("min_experience_years")
    years = profile.get("experience_years") or 0.0
    checks, frac = [], {}

    def skill_checks(skills, kind, required):
        hit = 0
        for s in skills:
            ev = find_evidence(text, s)
            hit += bool(ev)
            checks.append({
                "requirement": s, "kind": kind, "required": required, "met": bool(ev),
                "candidate_value": "Yes" if ev else "No",
                "evidence": ev["quote"] if ev else None,
                "evidence_type": ev["type"] if ev else None,
            })
        return hit / len(skills)

    if must:
        frac["must"] = skill_checks(must, "must_have_skill", True)
    if min_exp:
        jobs = [f"{e.get('title', '?')} — {e.get('company', '?')} ({e.get('start')} to {e.get('end')})"
                for e in profile.get("experience", [])]
        met = years >= min_exp
        checks.append({
            "requirement": "Experience", "kind": "experience", "required": True, "met": met,
            "required_value": f"{_fmt_years(min_exp)}+ years", "candidate_value": f"{_fmt_years(years)} years",
            "evidence": "; ".join(jobs)[:400] if jobs else "No dated work history found in resume",
            "evidence_type": profile.get("experience_source"),
        })
        frac["exp"] = min(years / min_exp, 1.0)  # partial credit, but `met` stays strict
    if nice:
        frac["nice"] = skill_checks(nice, "nice_to_have_skill", False)

    weights = {"must": W_MUST, "exp": W_EXP, "nice": W_NICE}
    used = sum(weights[k] for k in frac)  # redistribute weight of components the JD doesn't have
    score = round(100 * sum(frac[k] * weights[k] for k in frac) / used, 1) if used else 0.0
    meets_all = all(c["met"] for c in checks if c["required"])
    return {"candidate_id": candidate.id, "score": score, "meets_all_required": meets_all,
            "experience_years": years, "checks": checks}


def rank_and_shortlist(scored: list[dict], limit: int | None) -> list[dict]:
    """Qualified candidates first, then by score; ties broken by experience."""
    scored = sorted(scored, key=lambda r: (not r["meets_all_required"], -r["score"], -(r["experience_years"] or 0)))
    picked = 0
    for i, r in enumerate(scored, 1):
        r["rank"] = i
        ok = r["meets_all_required"] and (not limit or picked < limit)
        r["shortlisted"] = ok
        picked += ok
    return scored
