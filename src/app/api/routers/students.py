from typing import Annotated, Optional, List
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
from core.schemas.student import StudentBase, StudentCreate
from core.schemas.grade import GradeBase
from core.schemas.teacher import TeacherBase
from core.db import MongoClient
from api.dependencies import (
  get_mongo_client,
  get_current_user
)
import crud

router = APIRouter(tags=["Students"])

@router.post("/create",
  status_code=status.HTTP_201_CREATED,
  response_model=StudentBase,
  dependencies=[Security(get_current_user, scopes=["admin"])])
async def create_student(
  create_student: Annotated[StudentCreate, Body()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)] 
):
  """
  Create a student account.
  """
  
  groups_db = mongo.get_database("groups")
  for degree in await groups_db.list_collection_names():
    collection = groups_db.get_collection(degree)
    if (group := await collection.find_one({"group": create_student.group})):
      break

  if not group:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="The student's group not found."
    )
  
  users_db = mongo.get_database("users")
  if await crud.get_user_by_username(users_db, username=create_student.edbo_id):
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail="User already exits."
    )

  student = StudentBase.model_validate(
    await crud.create_user(users_db, user=create_student.model_dump())
  )

  return student

@router.post("/{group}/all",
  status_code=status.HTTP_200_OK,
  response_model=List[StudentBase],
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def read_students(
  group: Annotated[str, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
) -> List[StudentBase]:
  """
  Fetch a list of all existing students from the given group.
  """
  
  users_db = mongo.get_database("users")
  return await crud.read_users(users_db, role="students", filter="group", value=group)

@router.post("/my/grades",
  status_code=status.HTTP_200_OK,
  response_model=GradeBase)
async def get_current_student_grades(
  grade_body: Annotated[GradeBase, Body()],
  user: Annotated[dict, Security(get_current_user, scopes=["student"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Returns the current student grades by `subject`.    
  """

  student = StudentBase.model_validate(user)

  grades_db = mongo.get_database("grades")
  grade = GradeBase.model_validate(
    await crud.get_grades(grades_db, edbo_id=student.edbo_id, group=student.group, subject=grade_body.subject, date=grade_body.date) 
  )
  return grade

@router.get("/my/grades/all",
  status_code=status.HTTP_200_OK,
  response_model=List[GradeBase])
async def get_current_student_all_grades(
  user: Annotated[StudentBase, Security(get_current_user, scopes=["student"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  date: Annotated[Optional[str], Query()] = None
):
  """
  Returns all grades for the current user.
  """

  student = StudentBase.model_validate(user)

  grades_db = mongo.get_database("grades")
  grades = await crud.get_grades(grades_db, edbo_id=student.edbo_id, group=student.group, date=date)
  return grades

@router.post("{edbo_id}/grades",
  status_code=status.HTTP_200_OK,
  response_model=GradeBase,
  response_model_exclude_none = True,
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def get_student_grades(
  edbo_id: Annotated[int, Path()],
  grade_body: Annotated[GradeBase, Body()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
):
  """
  Fetch the specified student's subject grades.
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
  grade = GradeBase.model_validate(
    await crud.get_grades(grades_db, edbo_id=edbo_id, group=student.group, subject=grade_body.subject, date=grade_body.date)
  )  
  return grade

@router.get("{edbo_id}/grades/all",
  status_code=status.HTTP_200_OK,
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def get_student_all_grades(
  edbo_id: Annotated[int, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  date: Annotated[Optional[str], Query()] = None,
):
  """
  Fetch all subject grades. 
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
  grades = crud.get_grades(grades_db, edbo_id=edbo_id, group=student.group, date=date)
  return grades

@router.get("/disciplines",
  status_code=status.HTTP_200_OK)
async def get_student_disciplines(
  user: Annotated[dict, Security(get_current_user, scopes=["student"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Fetch the student's disciplines.
  """
  student = StudentBase.model_validate(user)
  
  disciplines = {}
  groups_db = mongo.get_database("groups")
  collection = groups_db.get_collection(student.degree)
  if not (group := await collection.find_one({"group": student.group})):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Group not found."
    )
  
  users_db = mongo.get_database("users")
  collection = users_db.get_collection("teachers")
  for k, v in group.get("disciplines").items():
    disciplines.update({
      k: TeacherBase.model_validate(**await collection.find_one({"edbo_id": v}))
    })
  return disciplines