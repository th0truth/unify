from typing import Union

from .base import BaseCRUD

class GradeCRUD(BaseCRUD):
  def __init__(self, db):
    super().__init__(db)

  @staticmethod
  async def get_grade_system(grade_system: dict, subject: str) -> Union[str, None]:
    if grade_system is None: return
    for system, subjects in grade_system.items():
      if subject in subjects:
        return system
