# AI Recruiter Agent (Sarvam-105B + FastAPI + PostgreSQL + React)

HR uploads 100+ resumes, pastes a JD and says: *"Shortlist candidates with FastAPI, Python,
PostgreSQL and 2+ years."* The agent parses the JD, loads candidates from PostgreSQL, scores
each one with **verbatim resume evidence**, proposes a shortlist, waits for **human approval**,
then produces an Excel file.

## Run it
```bash
docker compose up -d                       # PostgreSQL
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                       # put your SARVAM_API_KEY in it
uvicorn app.main:app --reload              # API on :8000  (docs at /docs)

cd ../frontend && npm install && npm run dev   # UI on :5173
```

## Architecture
```
HR -> React UI -> FastAPI -> Agent loop --tools--> parse_jd (Sarvam)        -> Requirements
                                         |        retrieve_candidates (PG) -> candidates
                                         |        match_candidates         -> evidence checks
                                         |        rank_shortlist / save_results
                                         '-> request_approval  == STOP, human reviews ==
HR clicks Approve -> POST /approve -> excel_export -> Download
```
Where the LLM is used: resume extraction, JD parsing, choosing the next tool, answering follow-up
questions. Where it is NOT used (on purpose): matching, scoring, evidence, experience math, Excel.

## Backend files

| File | What it does / why it exists |
|---|---|
| `app/config.py` | Settings from `.env` (API key, model name, DB URL, worker count). One place to tune; no secrets in code. |
| `app/database.py` | SQLAlchemy engine, session factory, and the `get_db` dependency (one session per request). Sync style: simpler, FastAPI threads it. |
| `app/models.py` | Tables: `candidates` (raw text + JSONB profile), `screenings` (JD, structured requirements, status, agent trace), `screening_results` (score, shortlisted flag, JSONB `checks` = the evidence). |
| `app/schemas.py` | `Requirements` (validates/cleans what the LLM returns for the JD: dedupes skills, coerces numbers), request bodies, and JSON serializers for the UI. |
| `app/llm/sarvam.py` | Client for `https://api.sarvam.ai/v1/chat/completions` with header `api-subscription-key`. Handles retries, `<think>` stripping, JSON-mode fallback, empty-reply-from-reasoning errors. |
| `app/services/file_reader.py` | PDF/DOCX/TXT -> text. Strips NUL bytes (Postgres rejects them). |
| `app/services/skills.py` | Alias table (Postgres = PostgreSQL = psql) and the whole-word regex builder so `sql` never matches inside `PostgreSQL`. |
| `app/services/resume_parser.py` | LLM extracts name/jobs/dates/education. **Code** computes years of experience from dates and merges overlapping jobs. Failures still leave the resume searchable. |
| `app/services/jd_parser.py` | HR request + JD -> `Requirements` JSON (must-have, nice-to-have, min years, top-N). HR's sentence overrides the JD on conflict. |
| `app/services/matcher.py` | The engine. For each requirement finds the best resume line (prefers lines describing real work over a bare skills list), computes the score (60% must-have, 25% experience, 15% nice-to-have; weights re-normalise when a JD lacks a part), ranks, shortlists. |
| `app/services/excel_export.py` | Builds Summary / Shortlist / All Candidates / Evidence sheets with openpyxl. Only called after approval. |
| `app/agent/tools.py` | The six tools + shared working memory `Ctx`. A tool can halt the run to ask HR a question (e.g. JD had no criteria). |
| `app/agent/agent.py` | The planner/executor loop, per-step trace saved to the DB (live UI), and `answer_question` (LLM answers only from stored evidence). |
| `app/routers/candidates.py` | Bulk upload (fast) + background parsing, list, delete. |
| `app/routers/agent.py` | `POST /api/agent/screen` starts a run; `POST /api/agent/ask/{id}` follow-up questions. |
| `app/routers/screenings.py` | List/get results, HR override per candidate, **approve** (creates Excel), download. |
| `app/main.py` | Creates the app, CORS, tables on startup, mounts routers. |

## Frontend files (React + Vite; proxies /api to FastAPI)

| File | Purpose |
|---|---|
| `vite.config.js` | Dev server + `/api` proxy to :8000. |
| `src/api.js` | Every HTTP call in one place. |
| `src/App.jsx` | Layout, sidebar of past screenings, which screening is open. |
| `src/components/ResumePool.jsx` | Multi-file upload, live "parsing" counts. |
| `src/components/ScreenForm.jsx` | HR request + JD paste/upload. |
| `src/components/ScreeningView.jsx` | Live agent steps, results table, click-to-expand evidence, shortlist toggle, Approve, Download, follow-up Q&A. |
| `src/styles.css` | Styling, light/dark. |

## Known limits / next steps
- Scanned (image-only) PDFs need OCR; they are rejected with a clear message.
- Tables are created with `create_all`; add Alembic before changing the schema in production.
- No login yet: add auth + per-organisation scoping (`org_id` on every table) for multi-tenant use.
- Skill aliases are a small table; extend `skills.py` or add an LLM fallback for unknown skills.
- Evaluate with a labelled set of resumes: compare `checks` against human labels.
