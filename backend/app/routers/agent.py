"""Chat-style entry points for HR: start a screening, ask follow-ups."""
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..agent.agent import answer_question, run_screening
from ..database import get_db
from ..models import Screening
from ..schemas import AskIn
from ..services.file_reader import extract_text

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/screen")
def start_screening(
    background: BackgroundTasks,
    hr_request: str = Form(...),
    jd_text: str = Form(""),
    jd_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    """Creates the Screening row and returns immediately; the agent runs in the
    background and the UI polls GET /api/screenings/{id} to show its steps."""
    if jd_file and jd_file.filename:
        try:
            jd_text = extract_text(jd_file.filename, jd_file.file.read())
        except ValueError as e:
            raise HTTPException(400, str(e))
    s = Screening(hr_request=hr_request.strip(), jd_text=jd_text.strip(), status="running", trace=[], requirements={})
    db.add(s)
    db.commit()
    background.add_task(run_screening, s.id)
    return {"screening_id": s.id}


@router.post("/ask/{screening_id}")
def ask(screening_id: int, body: AskIn, db: Session = Depends(get_db)):
    s = db.get(Screening, screening_id)
    if not s or not s.results:
        raise HTTPException(404, "No finished screening with that id")
    return {"answer": answer_question(s, body.question, [m.model_dump() for m in body.history])}


# """Chat-style entry points for HR: start a screening, ask follow-ups."""
# from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
# from sqlalchemy.orm import Session

# from ..agent.agent import answer_question, run_screening
# from ..database import get_db
# from ..models import Screening
# from ..schemas import AskIn
# from ..services.file_reader import extract_text

# router = APIRouter(prefix="/api/agent", tags=["agent"])


# @router.post("/screen")
# def start_screening(
#     background: BackgroundTasks,
#     hr_request: str = Form(...),
#     jd_text: str = Form(""),
#     jd_file: UploadFile | None = File(None),
#     db: Session = Depends(get_db),
# ):
#     """Creates the Screening row and returns immediately; the agent runs in the
#     background and the UI polls GET /api/screenings/{id} to show its steps."""
#     if jd_file and jd_file.filename:
#         try:
#             jd_text = extract_text(jd_file.filename, jd_file.file.read())
#         except ValueError as e:
#             raise HTTPException(400, str(e))
#     s = Screening(hr_request=hr_request.strip(), jd_text=jd_text.strip(), status="running", trace=[], requirements={})
#     db.add(s)
#     db.commit()
#     background.add_task(run_screening, s.id)
#     return {"screening_id": s.id}


# @router.post("/ask/{screening_id}")
# def ask(screening_id: int, body: AskIn, db: Session = Depends(get_db)):
#     s = db.get(Screening, screening_id)
#     if not s or not s.results:
#         raise HTTPException(404, "No finished screening with that id")
#     return {"answer": answer_question(s, body.question)}
