from typing import Any, Optional

from pymongo.asynchronous.database import AsyncDatabase 
from core.config import ModelType

class BaseCRUD:
  def __init__(self, db: AsyncDatabase):
    self.db = db

  async def create(self, collection: str, model: ModelType):
    await self.db[collection].insert_one(model.model_dump())

  async def read(self, collection: str, filter: Any):
    return await self.db[collection].find_one(filter)

  async def update(self, collection: str, *, update: dict, filter: Any = {}):
    result = await self.db[collection].update_one(filter, update={"$set": update})
    return result.modified_count

  async def update_all(self, collection: str, *, update: dict, filter: Any = {}) -> int:
    result = await self.db[collection].update_many(filter, update={"$set": update})
    return result.modified_count
  
  async def read_all(self, collection: str, *, filter: Any = {}, projection: Optional[dict] = None, offset: int = 0, length: Optional[int] = None):
    objects = await self.db[collection].find(filter, projection=projection).to_list(length)
    return objects[offset:]