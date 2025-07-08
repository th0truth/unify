from pydantic import BaseModel, Field, EmailStr
from typing import Annotated, Optional, Dict, Any

PASSWORDstr = Annotated[str, Field(..., min_length=8, max_length=128)]

class UpdatePassword(BaseModel):
  current_password:  PASSWORDstr
  new_password: PASSWORDstr

class UpdateEmail(BaseModel):
  email: Optional[EmailStr] = None
  password: str

class MetaFile(BaseModel):
  metadata: Dict[str, Any]
  url: str

class PasswordRecovery(BaseModel):
  email: str
  new_password: PASSWORDstr