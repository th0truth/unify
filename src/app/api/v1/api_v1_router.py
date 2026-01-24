from fastapi import APIRouter
from .routers import (
  google_auth,
  auth,
  teachers,
  user,
  users,
  groups,
  students,
  schedule
)

# Initialize v1 router
api_v1_router = APIRouter()

# Include routers
api_v1_router.include_router(google_auth.router, prefix="/auth")
api_v1_router.include_router(auth.router, prefix="/auth")
api_v1_router.include_router(user.router, prefix="/user")
api_v1_router.include_router(users.router, prefix="/users")
api_v1_router.include_router(groups.router, prefix="/groups")
api_v1_router.include_router(students.router, prefix="/students")
api_v1_router.include_router(teachers.router, prefix="/teachers")
api_v1_router.include_router(schedule.router, prefix="/schedule")