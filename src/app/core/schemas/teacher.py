from pydantic import BaseModel
from datetime import datetime

from .user import UserBase
from .group import LocalizedGroup
from .etc import PASSWORDstr

class TeacherBase(UserBase):
  disciplines: list
  specialities: list

class TeacherCreate(TeacherBase):
  scopes: list = [
    "teacher"
  ]
  role: str = "teacher"
  acc_date: datetime
  password: PASSWORDstr

class TeacherGroup(BaseModel):
  degree: str
  course: int
  group: LocalizedGroup
  specialty: str