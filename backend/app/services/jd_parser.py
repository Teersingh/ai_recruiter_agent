"""HR request + job description -> structured, validated Requirements.

The HR sentence ("Shortlist candidates with FastAPI, Python, PostgreSQL and 2+
years") wins over the JD body when they conflict, because it is the most
specific, most recent instruction."""
from ..llm.sarvam import llm
from ..schemas import Requirements

SYSTEM = """You convert a hiring request and job description into structured requirements.
Reply with ONLY a JSON object:
{"role_title": str,
 "must_have_skills": [str],          // hard requirements
 "nice_to_have_skills": [str],       // preferred / bonus only
 "min_experience_years": number|null,
 "shortlist_limit": integer|null,    // only if HR asks for "top N"
 "notes": str}                       // anything important you could not encode
Rules: skills must be short canonical names (e.g. "PostgreSQL", not "experience with PostgreSQL databases").
Only include skills explicitly stated; never infer. Skills HR names in the request are must-haves.
If the request conflicts with the JD, the request wins."""


def parse_requirements(hr_request: str, jd_text: str) -> Requirements:
    user = f"HR REQUEST:\n{hr_request}\n\nJOB DESCRIPTION:\n{jd_text[:10000] or '(none provided)'}"
    data = llm.chat_json([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}])
    return Requirements.model_validate(data)
