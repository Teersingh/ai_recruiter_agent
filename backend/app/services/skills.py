"""Skill aliases + the regex used to find a skill inside resume text.

Why: HR writes "PostgreSQL", a candidate writes "Postgres" or "psql". Without
aliases we would wrongly reject them. Matching is deterministic (regex), not
LLM-guessed, so a "Yes" always points at real words in the resume."""
import re
from functools import lru_cache

ALIASES = {
    "python": ["python", "python3"],
    "fastapi": ["fastapi", "fast api", "fast-api"],
    "postgresql": ["postgresql", "postgres", "psql", "postgre sql"],
    "javascript": ["javascript", "ecmascript"],
    "node.js": ["node.js", "nodejs", "node js"],
    "react": ["react", "reactjs", "react.js"],
    "mongodb": ["mongodb", "mongo db"],
    "aws": ["aws", "amazon web services"],
    "gcp": ["gcp", "google cloud"],
    "kubernetes": ["kubernetes", "k8s"],
    "machine learning": ["machine learning", "ml"],
    "rest api": ["rest api", "rest apis", "restful", "restful api"],
    "sqlalchemy": ["sqlalchemy", "sql alchemy"],
    "ci/cd": ["ci/cd", "cicd", "ci cd"],
}
_REVERSE = {a: canon for canon, als in ALIASES.items() for a in als}


def aliases_for(skill: str) -> list[str]:
    s = skill.strip().lower()
    canon = _REVERSE.get(s, s)
    return list(dict.fromkeys([s, *ALIASES.get(canon, [])]))


@lru_cache(maxsize=512)
def skill_pattern(skill: str) -> re.Pattern:
    """Whole-word, case-insensitive. 'sql' must NOT match inside 'PostgreSQL',
    and 'C' must not match 'C++', hence the look-arounds instead of \\b."""
    alts = []
    for a in aliases_for(skill):
        tail = r"(?![A-Za-z0-9+#])" if a[-1].isalnum() else r"(?![A-Za-z0-9])"
        alts.append(r"(?<![A-Za-z0-9])" + re.escape(a) + tail)
    return re.compile("|".join(alts), re.I)
