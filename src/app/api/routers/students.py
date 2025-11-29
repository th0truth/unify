from typing import Annotated, List
from fastapi import (
  HTTPException,
  APIRouter,
  status,
  Security,
  Depends,
  Query,
  Path,
  Body
)
from datetime import timedelta
import json

from core.config import settings

from core.schemas.student import StudentBase, StudentCreate
from core.schemas.grade import GradeBase
from core.schemas.teacher import TeacherBase
from core.db import MongoClient
from redis.asyncio import Redis
from api.dependencies import (
  get_mongo_client,
  get_redis_client,
  get_current_user
)
from crud import BaseCRUD, UserCRUD, StudentCRUD

router = APIRouter(tags=["Students"])

@router.post("/",
  status_code=status.HTTP_201_CREATED,
  dependencies=[Security(get_current_user, scopes=["admin"])])
async def create_student(
  create_student: Annotated[StudentCreate, Body()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)] 
):
  """
  Creates a student account.
  """
  groups_db = mongo.get_database("groups")
  for degree in await groups_db.list_collection_names():
    if (group := await groups_db[degree].find_one({"group.ua": create_student.group.ua})):
      break
  if not group:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="The student's group not found."
    )
  
  # Check if the user already exists
  users_db = mongo.get_database("users")
  if await UserCRUD(users_db).find(username=create_student.edbo_id):
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail="User already exists."
    )

  # Create a student account
  await UserCRUD(users_db).create(create_student)

  return {"message": "The student account was created successfully."}


@router.post("/{group}/all",
  status_code=status.HTTP_200_OK,
  response_model=List[StudentBase],
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def read_students(
  group: Annotated[str, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
) -> List[StudentBase]:
  """
  Returns a list of all existing students from the given group.
  """
  users_db = mongo.get_database("users")
  return await UserCRUD(users_db).read_all("students", filter={"group.ua": group})


@router.post("/my/grades",
  status_code=status.HTTP_200_OK)
async def get_current_student_grades(
  grade_body: Annotated[GradeBase, Body()],
  user: Annotated[dict, Security(get_current_user, scopes=["student"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  date: Annotated[str, Query()] = None
):
  """
  Returns all grades for the current student.    
  """
  student = StudentBase.model_validate(user)

  grades_db = mongo.get_database("grades")
  grades = await StudentCRUD(grades_db).get_grades(edbo_id=student.edbo_id, group=student.group.ua, subject=grade_body.subject, date=date) 
  return grades


@router.get("/my/grades/all",
  status_code=status.HTTP_200_OK)
async def get_current_student_all_grades(
  user: Annotated[StudentBase, Security(get_current_user, scopes=["student"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  date: Annotated[str, Query()] = None
):
  """
  Returns all grades for the current student.
  """
  student = StudentBase.model_validate(user)

  grades_db = mongo.get_database("grades")
  grades = await StudentCRUD(grades_db).get_grades(edbo_id=student.edbo_id, group=student.group.ua, date=date)
  return grades


@router.post("/{edbo_id}/grades",
  status_code=status.HTTP_200_OK,
  response_model_exclude_none = True,
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def get_student_grades(
  edbo_id: Annotated[int, Path()],
  grade_body: Annotated[GradeBase, Body()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  date: Annotated[str, Query()] = None
):
  """
  Returns all grades for the specified student's subject.
  """
  users_db = mongo.get_database("users")
  collection = users_db.get_collection("students")
  if not (user := await collection.find_one({"edbo_id": edbo_id})):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Student not found."
    )
  student = StudentBase.model_validate(user)
  
  grades_db = mongo.get_database("grades")
  grades = await StudentCRUD(grades_db).get_grades(edbo_id=edbo_id, group=student.group.ua, subject=grade_body.subject, date=date)
  return grades


@router.get("/{edbo_id}/grades/all",
  status_code=status.HTTP_200_OK,
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def get_student_all_grades(
  edbo_id: Annotated[int, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  date: Annotated[str, Query()] = None
):
  """
  Returns all grades for the student's subjects.
  """
  users_db = mongo.get_database("users")
  collection = users_db.get_collection("students")
  if not (user := await collection.find_one({"edbo_id": edbo_id})):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Student not found."
    )
  student = StudentBase.model_validate(user)

  grades_db = mongo.get_database("grades")
  grades = await StudentCRUD(grades_db).get_grades(edbo_id=edbo_id, group=student.group.ua, date=date)
  return grades


@router.get("/disciplines",
  status_code=status.HTTP_200_OK)
async def get_student_disciplines(
  user: Annotated[dict, Security(get_current_user, scopes=["student"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  redis: Annotated[Redis, Depends(get_redis_client)]
):
  """
  Returns the current student's disciplines.
  """
  student = StudentBase.model_validate(user)

  redis_key = f"cache:group:{student.group.ua}:disciplines"

  # Check if group disciplines exist in Redis cache
  if (disciplines_cache := await redis.get(redis_key)):
    try:
      disciplines = json.loads(disciplines_cache)
      return disciplines
    except json.JSONDecodeError:
      pass
    
  else:
    disciplines = {}
    groups_db = mongo.get_database("groups")
    for degree in await groups_db.list_collection_names():
      if (student_group := await BaseCRUD(groups_db).read(degree, filter={"group.ua": student.group.ua})):
        break
    if not student_group:
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Group not found."
      )
    
    users_db = mongo.get_database("users")
    # collection = users_db.get_collection("teachers")
    for subject, edbo_id in student_group.get("disciplines").items():
      if (teacher := await UserCRUD(users_db).find(username=edbo_id)):
        disciplines.update({
          subject: TeacherBase(**teacher).model_dump()
        })

    # Store group disciplines in Redis cache
    await redis.setex(redis_key, timedelta(minutes=settings.CACHE_EXPIRE_MINUTES).seconds, value=json.dumps(disciplines))

    return disciplines