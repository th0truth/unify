__all__ = [
  "BaseCRUD",
  "UserCRUD",
  "StudentCRUD",
  "GradeCRUD",
  "ScheduleCRUD",
  "GroupCRUD",
]

from .base import BaseCRUD
from .user import UserCRUD
from .student import StudentCRUD
from .grade import GradeCRUD
from .schedule import ScheduleCRUD
from .group import GroupCRUD