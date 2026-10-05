"""Screening results, human review, approval and download."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Screening, ScreeningResult
from ..schemas import OverrideIn, result_out, screening_out
from ..services.excel_export import build_workbook

router = APIRouter(prefix="/api/screenings", tags=["screenings"])


def _get(db: Session, sid: int) -> Screening:
    s = db.get(Screening, sid)
    if not s:
        raise HTTPException(404, "Screening not found")
    return s


@router.get("")
def list_screenings(db: Session = Depends(get_db)):
    return [screening_out(s) for s in db.query(Screening).order_by(Screening.id.desc()).limit(50)]


@router.get("/{sid}")
def get_screening(sid: int, db: Session = Depends(get_db)):
    return screening_out(_get(db, sid), with_results=True)


@router.patch("/{sid}/results/{rid}")
def override_decision(sid: int, rid: int, body: OverrideIn, db: Session = Depends(get_db)):
    """Human-in-the-loop: HR can add or remove a candidate before approving."""
    s = _get(db, sid)
    if s.status == "approved":
        raise HTTPException(409, "Already approved - start a new screening to change decisions")
    r = db.get(ScreeningResult, rid)
    if not r or r.screening_id != sid:
        raise HTTPException(404, "Result not found")
    r.overridden = body.shortlisted != r.meets_all_required  # differs from what the criteria alone say
    r.shortlisted = body.shortlisted
    db.commit()
    return result_out(r)


@router.post("/{sid}/approve")
def approve(sid: int, db: Session = Depends(get_db)):
    """The ONLY place the Excel file is generated: after an explicit human click."""
    s = _get(db, sid)
    if s.status not in ("awaiting_approval", "approved"):
        raise HTTPException(409, f"Cannot approve a screening that is '{s.status}'")
    s.excel_path = build_workbook(s)
    s.status, s.approved_at = "approved", datetime.now(timezone.utc)
    db.commit()
    return screening_out(s)


@router.get("/{sid}/download")
def download(sid: int, db: Session = Depends(get_db)):
    s = _get(db, sid)
    if s.status != "approved" or not s.excel_path:
        raise HTTPException(409, "Approve the shortlist first")
    return FileResponse(s.excel_path, filename=f"shortlist_{s.id}.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
