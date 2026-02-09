from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from .user import UserInitial
from .group import LocalizedGroup
from .etc import MetaFile


class ScheduleDate(BaseModel):
  startAt: datetime
  endAt: datetime


class ScheduleBase(BaseModel):
  subject: str = Field(max_length=50, min_length=1)
  position: int
  classroom: int
  event: ScheduleDate
  date: str
  topic: str = Field(max_length=128)
  homework: str = Field(max_length=128)

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
