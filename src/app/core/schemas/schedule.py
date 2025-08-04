from typing import Optional, List
from pydantic import BaseModel

from .user import UserInitial
from .group import LocalizedGroup
from .etc import MetaFile

class ScheduleBase(BaseModel):
  subject: str
  position: int
  classroom: int
  date: str
  topic: str
  homework: str

class ScheduleCreate(ScheduleBase):
  group: LocalizedGroup
  date: str

class ScheduleUpdate(BaseModel):
  subject: Optional[str] = None
  position: Optional[int] = None
  classroom: Optional[int] = None
  date: Optional[str] = None
  topic: Optional[str] = None
  homework: Optional[str] = None

class SchedulePrivate(ScheduleCreate):
  teacher: Optional[UserInitial] = None
  teacher_edbo: Optional[int] = None
  grade: Optional[int] = None
  attachments: Optional[List[MetaFile]] = None
  lesson_id: str