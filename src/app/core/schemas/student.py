from datetime import datetime
from pydantic import Field

from .user import UserBase

class StudentBase(UserBase):
  speciality: str
  degree: str
  course: int
  group: str
  start_of_study: str
  complete_of_study: str
  class_teacher_edbo: int

class StudentCreate(StudentBase):
  role: str = "students"
  acc_date: datetime
  password: str = Field(..., min_length=8, max_length=256)