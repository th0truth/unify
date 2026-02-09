import math

from passlib.context import CryptContext
from abc import ABC, abstractmethod

class Hash:
  context = CryptContext(schemes=["argon2"], deprecated="auto")

  @classmethod
  def hash(cls, plain: str) -> str:
    """Return hashed password."""
    return cls.context.hash(secret=plain)
          
  @classmethod
  def verify(cls, plain: str, hashed: str) -> bool:
    """Return bool type of the verified password."""
    return cls.context.verify(secret=plain, hash=hashed)
    

class DBConnection(ABC):
  """Abstract base class for DB instance client."""
  
  @classmethod
  @abstractmethod
  async def connect(cls):
    """Establish instance connection."""
    pass

  @classmethod
  @abstractmethod
  async def close(cls):
    """Close instance connection."""
    pass


def convert_size(size_bytes: bytes):
  if not bytes:
    return "0B"
  size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
  i = int(math.floor(math.log(size_bytes, 1024)))
  p = math.pow(1024, i)
  s = round(size_bytes / p, 2)
  return "%s %s" % (s, size_name[i])

