from typing import Annotated
from fastapi import (
  HTTPException,
  APIRouter,
  status,
  Security,
  Depends,
  Path,
  Body
)
from core.schemas.student import StudentBase
from core.schemas.teacher import TeacherBase, TeacherCreate
from core.schemas.grade import SetGrade
from core.db import MongoClient
from api.dependencies import (
  get_mongo_client,
  get_current_user
)
import crud

router = APIRouter(tags=["Teachers"])

@router.post("/create",
  status_code=status.HTTP_201_CREATED,
  response_model=TeacherBase,
  dependencies=[Security(get_current_user, scopes=["admin"])])
async def create_teacher(
  create_teacher: Annotated[TeacherCreate, Body()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Creates a teacher account.
  """
  users_db = mongo.get_database("users")
  teacher = TeacherBase.model_validate(
    await crud.create_user(users_db, user=create_teacher)  
  )
  return teacher

@router.patch("/assessment/{edbo_id}",
  status_code=status.HTTP_200_OK)
async def student_assessment(
  edbo_id: Annotated[int, Path()],
  grade_body: Annotated[SetGrade, Body()],
  user: Annotated[dict, Security(get_current_user, scopes=["teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Assesses the student.
  """
  teacher = TeacherBase.model_validate(user)

  users_db = mongo.get_database("users")
  collection = users_db.get_collection("students")
  if not (user := await collection.find_one({"edbo_id": edbo_id})):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Student not found."
    )
  student = StudentBase.model_validate(user)

  if grade_body.subject not in teacher.disciplines:
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="You don't have access to this discipline."
    )
  
  grades_db = mongo.get_database("grades")
  collection = grades_db.get_collection(student.group)

  if not (await collection.find_one_and_update(
    filter={"edbo_id": edbo_id},
    update={"$set": {f"disciplines.{grade_body.subject}.{grade_body.date}": grade_body.grade}}
  )):
    await collection.insert_one(
      {"edbo_id": edbo_id,
       "disciplines": {
         grade_body.grade: {
           grade_body.date: grade_body.grade
         }
       }}
    )

  raise HTTPException(
    status_code=status.HTTP_200_OK,
    detail="Student successfully assessed."
  )