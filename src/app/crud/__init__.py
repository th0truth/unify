__all__ = [
  "BaseCRUD",
  "UserCRUD",
  "StudentCRUD",
  "GradeCRUD"
]

from .base import BaseCRUD
from .user import UserCRUD
from .student import StudentCRUD
from .grade import GradeCRUD