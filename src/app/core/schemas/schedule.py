from typing import Optional, List
from pydantic import BaseModel

from .user import UserInitial
from .etc import MetaFile

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
  teacher: Optional[UserInitial] = None
  teacher_edbo: Optional[int] = None
  grade: Optional[int] = None
  attachments: Optional[List[MetaFile]] = None
  lesson_id: str