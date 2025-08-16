from typing import Optional, List, Union

from core.config import ModelType
from core.security.utils import Hash

from .base import BaseCRUD

class UserCRUD(BaseCRUD):
  def __init__(self, db):
    super().__init__(db)

  async def find(self, *, username: Union[str, int], exclude: Optional[List] = None) -> dict:
    """Fetch user profile from MongoDB database."""
    for collection in await self.db.list_collection_names():
      if (user := await self.db[collection].find_one({"edbo_id": int(username)} if isinstance(username, int) or username.isdigit() else {"email.address": username})):
        break
    if exclude:
      for key in exclude:
        user.pop(key)
    return user

  async def create(self, user: ModelType):
    user.password = Hash.hash(plain=user.password)
    await self.db[user.role].insert_one(user.model_dump())
    return user

  async def update(self, username: Union[str, int], update: dict) -> Union[dict, None]:
    """Updates a user profile."""
    if not (user := await self.find(username=username)):
      return
    return await self.db[user.get("role")].find_one_and_update(
      filter=user,
      update={"$set": update}
    )

  async def authenticate(self, *, username: Union[str, int], plain_pwd: str, exclude: Optional[List] = None) -> Union[dict, None]:
    """Authenticate user using credentials."""
    user = await self.find(username=username)
    if not user or not Hash.verify(plain_pwd, user.get("password")):
      return None
    if exclude:
      for key in exclude:
        user.pop(key)
    return user