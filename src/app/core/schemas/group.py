from pydantic import BaseModel
from datetime import datetime
from typing import Any

class GroupBase(BaseModel):
  degree: str
  course: int
  group: str
  specialty: str
  disciplines: Any
  class_teacher_edbo: int

class GroupCreate(GroupBase):
  date: datetime