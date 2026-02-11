from typing import Optional, List, Union
from fastapi import status, HTTPException

from .base import BaseCRUD


class ScheduleCRUD(BaseCRUD):
  def __init__(self, db):
    super().__init__(db)
    self.collection = "lessons"

  async def create(self, lesson: dict) -> dict:
    """Creates a lesson."""
    await self.db[self.collection].insert_one(lesson)
    return lesson

  async def get_by_id(self, lesson_id: str, exclude: Optional[List] = None) -> Union[dict, None]:
    """Fetches lesson by ID."""
    if not (lesson := await self.db[self.collection].find_one({"lesson_id": lesson_id})):
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Lesson not found."
      )
    if exclude:
      for key in exclude:
        lesson.pop(key, None)
    return lesson

  async def get_by_group(self, group: str) -> List[dict]:
    """Fetches all lessons for a group."""
    return await self.db[self.collection].find({"group.en": group}).to_list()

  async def get_by_teacher(self, teacher_edbo: int) -> List[dict]:
    """Fetches all lessons for a teacher."""
    return await self.db[self.collection].find({"teacher_edbo": teacher_edbo}).to_list()

  async def update(self, lesson_id: str, update: dict) -> dict:
    """Updates a lesson by ID."""
    if not (result := await self.db[self.collection].find_one_and_update(
      filter={"lesson_id": lesson_id},
      update={"$set": update},
      return_document=True,
    )):
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Lesson not found."
      )
    return result

  async def delete(self, lesson_id: str) -> bool:
    """Deletes a lesson by ID."""
    if not (result := await self.db[self.collection].find_one_and_delete({"lesson_id": lesson_id})):
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Lesson not found."
      )
    return True

  async def exists(self, lesson_id: str) -> bool:
    """Checks if lesson exists."""
    return await self.db[self.collection].find_one({"lesson_id": lesson_id}) is not None

  async def exists_for_teacher(self, lesson_id: str, teacher_edbo: int) -> bool:
    """Checks if lesson exists for specific teacher."""
    return await self.db[self.collection].find_one({"lesson_id": lesson_id, "teacher_edbo": teacher_edbo}) is not None

  async def add_attachments(self, lesson_id: str, attachments: List[dict]) -> bool:
    """Adds attachments to a lesson."""
    result = await self.db[self.collection].update_one(
      filter={"lesson_id": lesson_id},
      update={"$push": {"attachments": {"$each": attachments}}},
    )
    return result.modified_count > 0

  async def remove_attachment(self, lesson_id: str, file_id: str) -> bool:
    """Removes an attachment from a lesson."""
    result = await self.db[self.collection].update_one(
      filter={"lesson_id": lesson_id},
      update={"$pull": {"attachments": {"file_id": file_id}}},
    )
    return result.modified_count > 0

  async def has_attachment(self, lesson_id: str, file_id: str) -> Union[dict, None]:
    """Checks if lesson has specific attachment."""
    return await self.db[self.collection].find_one({
      "lesson_id": lesson_id,
      "attachments": {"$elemMatch": {"file_id": file_id}}}
  )