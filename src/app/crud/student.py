from fastapi import status, HTTPException
from core.schemas.student import StudentBase

from .base import BaseCRUD

class StudentCRUD(BaseCRUD):
  def __init__(self, db):
    super().__init__(db)

  async def _fetch(self, edbo_id: int):
    if not (user := await self.db["students"].find_one({"edbo_id": edbo_id})):
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Student not found."
      )
    return StudentBase.model_validate(user)

  async def get_grades(self, *, edbo_id: int, group: str, **kwargs) -> dict:
    """Get student subject grades."""
    grades_doc: dict = await self.db[group].find_one({"edbo_id": edbo_id})
    if not grades_doc: return {}
    disciplines: dict = grades_doc.get("disciplines", {})
    subject, date = kwargs.get("subject"), kwargs.get("date")
    if subject and date: return disciplines.get(subject, {}).get(date)
    if subject: return disciplines.get(subject, {})
    result = {}
    for subject, records in disciplines.items():
      result[subject] = records.get(date) if date else records
    return result