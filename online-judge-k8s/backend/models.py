from pydantic import BaseModel, Field
from typing import Literal, Optional

Language = Literal["python", "cpp"]

class SubmitRequest(BaseModel):
    code: str = Field(..., min_length=1)
    language: Language = "python"
    problem_id: str = "sum"

class SubmitResponse(BaseModel):
    submission_id: str
    job_name: str
    status: str

class ResultResponse(BaseModel):
    submission_id: str
    job_name: str
    status: str
    result: Optional[dict] = None
