"""Application entry point: `uvicorn app.main:app --reload`."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .routers import agent, candidates, screenings


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)  # creates tables on first start (use Alembic once the schema evolves)
    yield


app = FastAPI(title="AI Recruiter Agent", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
for r in (candidates.router, agent.router, screenings.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True, "model": settings.sarvam_model, "llm_key_set": bool(settings.sarvam_api_key)}
