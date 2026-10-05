"""Resume pool endpoints. Upload is fast: we store the text immediately and let
a background task do the slow LLM extraction, so uploading 100 files returns
in seconds instead of minutes."""
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Candidate
from ..schemas import candidate_out
from ..services.file_reader import extract_text
from ..services.resume_parser import parse_many

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


@router.post("/upload")
def upload_resumes(background: BackgroundTasks, files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    created, errors = [], []
    for f in files:
        try:
            text = extract_text(f.filename or "", f.file.read())
            if len(text) < 30:
                raise ValueError("No readable text (scanned image PDF?)")
            c = Candidate(filename=f.filename, raw_text=text, profile={}, parse_status="pending")
            db.add(c)
            db.flush()
            created.append(c.id)
        except Exception as e:
            errors.append({"filename": f.filename, "error": str(e)})
    db.commit()
    if created:
        background.add_task(parse_many, created)
    return {"queued": len(created), "errors": errors}


@router.get("")
def list_candidates(db: Session = Depends(get_db)):
    rows = db.query(Candidate).order_by(Candidate.id.desc()).all()
    return {"candidates": [candidate_out(c) for c in rows],
            "counts": {s: sum(c.parse_status == s for c in rows) for s in ("pending", "parsed", "failed")}}


@router.delete("/{candidate_id}")
def delete_candidate(candidate_id: int, db: Session = Depends(get_db)):
    c = db.get(Candidate, candidate_id)
    if not c:
        raise HTTPException(404, "Candidate not found")
    db.delete(c)
    db.commit()
    return {"ok": True}
