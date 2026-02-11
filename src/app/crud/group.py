from typing import Optional, List, Union, Tuple
from fastapi import status, HTTPException

from .base import BaseCRUD

from core.config import ModelType

class GroupCRUD(BaseCRUD):
  def __init__(self, db):
    super().__init__(db)

  async def _find_collection(self, group_name: str) -> Tuple[str, dict]:
    """Finds which degree collection contains the group."""
    for degree in await self.db.list_collection_names():
      if group := await self.db[degree].find_one(
        {"$or": [{"group.en": group_name}, {"group.ua": group_name}]}
      ):
        return degree, group
    return None, None

  async def _find_collection_by_teacher(self, teacher_edbo: int) -> Tuple[str, dict]:
    """Finds which degree collection contains the group by teacher."""
    for degree in await self.db.list_collection_names():
      if group := await self.db[degree].find_one(
        {"class_teacher_edbo": teacher_edbo}
      ):
        return degree, group
    return None, None

  async def create(self, degree: str, group: dict) -> dict:
    """Creates a group in specified degree collection."""
    await self.db[degree].insert_one(group)
    return group

  async def get_by_name(self, group_name: str, exclude: Optional[List] = None) -> Union[dict, None]:
    """Fetches group by name (en or ua)."""
    degree, group = await self._find_collection(group_name)
    if not group:
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Group not found."
      )
    if exclude:
      for key in exclude:
        group.pop(key, None)
    return group
  
  async def get_by_teacher(self, teacher_edbo: int, exclude: Optional[List] = None) -> Union[dict, None]:
    """Fetches group by class teacher."""
    degree, group = await self._find_collection_by_teacher(teacher_edbo)
    if not group:
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Group not found.")
    if exclude:
      for key in exclude:
        group.pop(key, None)
    return group
  
  async def get_all(self) -> dict:
    """Fetches all groups organized by degree."""
    groups = {}
    for degree in await self.db.list_collection_names():
      group_list = await self.db[degree].find().to_list()
      groups.update({degree: group_list})
    return groups
  
  async def get_all_by_degree(self, degree: str) -> List[dict]:
    """Fetches all groups for a specific degree."""
    return await self.db[degree].find().to_list()
  
  async def exists(self, group_name: str) -> bool:
    """Checks if group exists by name."""
    _, group = await self._find_collection(group_name)
    return group is not None
  
  async def exists_with_conflict_check(self, group_en: str, group_ua: str) -> bool:
    """Checks if group exists checking both EN and UA names."""
    for degree in await self.db.list_collection_names():
      if await self.db[degree].find_one(
        {"$or": [{"group.en": group_en}, {"group.ua": group_ua}]}
      ):
        return True
    return False
  
  async def delete(self, group_name: str) -> bool:
    """Deletes a group by name."""
    degree, group = await self._find_collection(group_name)
    if not group:
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Group not found."
      )
      
    await self.db[degree].delete_one(group)
    return True
  
  async def degree_exists(self, degree: str) -> bool:
    """Checks if degree collection exists."""
    return degree in await self.db.list_collection_names()
  

  async def get_disciplines(self, group: dict, model: ModelType) -> dict:
    group.update(
      {"disciplines": [{
        discipline: model.model_validate(
          await self.db["teachers"].find_one({"edbo_id": edbo_id}))} for discipline, edbo_id in group["disciplines"].items()]
      }
    )
    return group