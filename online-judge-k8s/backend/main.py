import json
import uuid
import os
import redis
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from models import SubmitRequest, SubmitResponse, ResultResponse 
from sqlalchemy.orm import Session
from database import SessionLocal, Submission

app = FastAPI(title="Kubernetes Online Judge MVP (DB Version)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

Instrumentator().instrument(app).expose(app)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def health():
    return {"status": "ok", "service": "online-judge-backend-db"}

@app.post("/submit", response_model=SubmitResponse)
def submit(req: SubmitRequest, db: Session = Depends(get_db)):
    submission_id = uuid.uuid4().hex[:12]
    job_name = f"judge-job-{submission_id}"

    new_sub = Submission(
        task_id=submission_id,
        code=req.code,
        status="Queued"
    )
    db.add(new_sub)
    db.commit()

    try:
        redis_client.xadd("submission_stream", {
            "task_id": submission_id,
            "code": req.code,
            "language": req.language,
            "problem_id": str(getattr(req, "problem_id", "sum"))
        }, maxlen=1000, approximate=True)
    except Exception as exc:
        db.delete(new_sub)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to enqueue: {exc}")

    return SubmitResponse(submission_id=submission_id, job_name=job_name, status="Queued")

@app.get("/result/{submission_id}", response_model=ResultResponse)
def result(submission_id: str, db: Session = Depends(get_db)):
    sub = db.query(Submission).filter(Submission.task_id == submission_id).first()
    
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found in DB.")

    judge_result = None
    if sub.result:
        try:
            judge_result = json.loads(sub.result)
        except json.JSONDecodeError:
            judge_result = {"error": "JSON Parsing failed"}

    return ResultResponse(
        submission_id=submission_id,
        job_name=f"judge-job-{submission_id}",
        status=sub.status,
        result=judge_result,
    )