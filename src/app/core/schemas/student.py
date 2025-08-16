from datetime import datetime

from .user import UserBase
from .etc import PASSWORDstr
from .group import LocalizedGroup

class StudentBase(UserBase):
  speciality: str
  degree: str
  course: int
  group: LocalizedGroup
  start_of_study: str
  complete_of_study: str
  class_teacher_edbo: int

class StudentCreate(StudentBase):
  scopes: list = [
    "student"
  ]
  role: str = "students"
  acc_date: datetime
  password: PASSWORDstr