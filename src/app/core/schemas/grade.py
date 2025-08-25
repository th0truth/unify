from pydantic import BaseModel

class GradeBase(BaseModel):
  subject: str

class SetGrade(GradeBase):
  grade: int
  date: str

class GradeGroup(BaseModel):
  edbo_id: int
  disciplines: dict