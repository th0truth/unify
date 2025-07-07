from pydantic import BaseModel
from typing import Optional, Union

from .teacher import TeacherBase
from .user import UserBase

class ScheduleBase(BaseModel):
  subject: str
  position: int
  classroom: int
  date: str
  topic: str
  homework: str

class ScheduleCreate(ScheduleBase):
  group: str
  date: str

class SchedulePrivate(ScheduleCreate):
  teacher: Optional[Union[TeacherBase, UserBase]] = None 
  teacher_edbo: Optional[int] = None
  grade: Optional[int] = None
  lesson_id: str