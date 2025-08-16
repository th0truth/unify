from typing import Optional, List
from datetime import datetime
from pydantic import (
  BaseModel,
  EmailStr
)

class UserInitial(BaseModel):
  first_name: str
  middle_name: str
  last_name: str

class UserBase(UserInitial):
  edbo_id: int
  date_of_birth: str
  role: str

class UserPrivate(UserBase):
  acc_date: datetime
  email: Optional[EmailStr] = None
  phone_number: Optional[List[int]] = None
  password: Optional[str] = None
  scopes: list

class UserUpdate(UserBase):
  scopes: list