from typing import Literal
from pydantic import BaseModel

from .user import UserInitial


class GradeBase(BaseModel):
  subject: str


class SetGrade(GradeBase):
  grade_system: Literal["5-point", "12-point"]
  grade: int
  date: str


class GradeGroup(BaseModel):
  student: UserInitial
  edbo_id: int
  discipline: dict
