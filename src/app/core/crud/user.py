from typing import Optional, List, Union
from core.security.utils import Hash
from .base import BaseCRUD

class UserCRUD(BaseCRUD):
  def __init__(self, db):
    super().__init__(db)

  async def get_by_username(self, *, username: str | int, exclude: Optional[List] = None) -> dict:
    """Fetch user profile from MongoDB database."""
    for collection in await self.db.list_collection_names():
      user = await self.db[collection].find_one(
        {"edbo_id": int(username)} if isinstance(username, int) or username.isdigit() else {"email.address": username})
      if user: break
    if exclude:
      for key in exclude:
        user.pop(key)
    return user
  
  async def authenticate(self, *, username: str | int, plain_pwd: str, exclude: Optional[List] = None) -> Union[dict, None]:
    """Authenticate user using credentials."""
    user = await self.get_by_username(username=username)
    if not user or not Hash.verify(plain_pwd, user.get("password")):
      return None
    if exclude:
      for key in exclude:
        user.pop(key)
    return user