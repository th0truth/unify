from typing import Optional, List, Union

from core.config import ModelType
from .base import BaseCRUD

class GradeCRUD(BaseCRUD):
  def __init__(self, db):
    super().__init__(db)

  @staticmethod
  async def get_grade_system(grade_system: dict, subject: str) -> Union[str, None]:
    for system, subjects in grade_system.items():
      if subject in subjects:
        return system
    return