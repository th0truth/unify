from pydantic import BaseModel
from typing import Optional

class GradeBase(BaseModel):
  subject: str

class SetGrade(GradeBase):
  grade: int
  date: str