from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Any


class LocalizedGroup(BaseModel):
  en: str
  model_config = ConfigDict(extra="allow")


class GroupBase(BaseModel):
  degree: str
  course: int
  group: LocalizedGroup
  specialty: str
  disciplines: Any
  class_teacher_edbo: int


class GroupCreate(GroupBase):
  date: datetime
