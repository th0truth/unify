from pydantic import BaseModel
from typing import Optional

class GradeBase(BaseModel):
  subject: str
  date: Optional[str] = None

class SetGrade(GradeBase):
  grade: int