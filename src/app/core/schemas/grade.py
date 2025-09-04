from pydantic import BaseModel

from .user import UserInitial

class GradeBase(BaseModel):
  subject: str

class SetGrade(GradeBase):
  grade: int
  date: str

class GradeGroup(BaseModel):
  student: UserInitial
  edbo_id: int
  disciplines: dict