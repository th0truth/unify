from typing import Optional, List, Union
from core.security.utils import Hash
from .base import BaseCRUD

class UserCRUD(BaseCRUD):
  def __init__(self, db):
    super().__init__(db)

  async def authenticate(self, *, username: Union[str, int], plain_pwd: str, exclude: Optional[List] = None) -> Union[dict, None]:
    """Authenticate user using credentials."""
    user = await self.find(username=username)
    if not user or not Hash.verify(plain_pwd, user.get("password")):
      return None
    if exclude:
      for key in exclude:
        user.pop(key)
    return user
  
  async def find(self, *, username: Union[str, int], exclude: Optional[List] = None) -> dict:
    """Fetch user profile from MongoDB database."""
    for collection in await self.db.list_collection_names():
      if (user := await self.db[collection].find_one({"edbo_id": int(username)} if isinstance(username, int) or username.isdigit() else {"email.address": username})):
        break
    if exclude:
      for key in exclude:
        user.pop(key)
    return user