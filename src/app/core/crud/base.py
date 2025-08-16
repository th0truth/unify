from typing import Any

from pymongo.asynchronous.database import AsyncDatabase 
from core.config import ModelType

class BaseCRUD:
  def __init__(self, db: AsyncDatabase):
    self.db = db

  async def create(self, collection: str, model: ModelType):
    await self.db[collection].insert_one(model.model_dump())

  async def read(self, collection: str, filter: Any):
    return await self.db[collection].find_one(filter)  