from datetime import datetime

from .user import UserBase
from .etc import PASSWORDstr

class TeacherBase(UserBase):
  disciplines: list
  specialities: list

class TeacherCreate(TeacherBase):
  scopes: list = [
    "teacher"
  ]
  role: str = "teachers"
  acc_date: datetime
  password: PASSWORDstr