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

from core.logger import logger
from core.config import settings

from core.schemas.user import UserInitial
from core.schemas.student import StudentBase, StudentCreate
from core.schemas.grade import GradeBase, SetGrade, GradeGroup
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

@router.post("",
  status_code=status.HTTP_201_CREATED,
  operation_id="CreateStudent",
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
    if (group := await groups_db[degree].find_one(
      {"$or": [
        {"group.en": create_student.group.en},
        {"group.ua": create_student.group.ua}
      ]}
    )):
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



@router.get("/disciplines",
  status_code=status.HTTP_200_OK,
  operation_id="ReadStudentDisciplines")
async def get_student_disciplines(
  user: Annotated[dict, Security(get_current_user, scopes=["student"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  redis: Annotated[Redis, Depends(get_redis_client)]
):
  """
  Returns the current student's disciplines.
  """
  student = StudentBase.model_validate(user)

  redis_key = f"cache:groups:{student.group.en}:disciplines"

  # Check if group disciplines exist in Redis cache
  if (disciplines_cache := await redis.get(redis_key)):
    try:
      return json.loads(disciplines_cache)
    except json.JSONDecodeError as err:
      logger.error({"message": "[x] Failed decode student's disciplines from Redis cache.", "detail": str(err)}, exc_info=True)

  disciplines = {}
  groups_db = mongo.get_database("groups")
  for degree in await groups_db.list_collection_names():
    if (student_group := await BaseCRUD(groups_db).read(degree, filter={
      "$or": [
        {"group.en": student.group.en},
        {"group.ua": student.group.ua}
      ]
    })):
      break
  if not student_group:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Group not found."
    )
   
  users_db = mongo.get_database("users")
  for subject, edbo_id in student_group.get("disciplines").items():
    if (teacher := await UserCRUD(users_db).find(username=edbo_id)):
      disciplines.update({
      subject: TeacherBase(**teacher).model_dump()
    })
  
  # Store group disciplines in Redis cache
  await redis.setex(redis_key, timedelta(minutes=settings.CACHE_EXPIRE_MINUTES).seconds, value=json.dumps(disciplines))

  return disciplines


@router.get("/{group}",
  status_code=status.HTTP_200_OK,
  operation_id="ReadStudentsByGroup",
  response_model=List[StudentBase],
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def get_students_by_group(
  group: Annotated[str, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
) -> List[StudentBase]:
  """
  Returns a list of all existing students from the given group.
  """
  users_db = mongo.get_database("users")
  return await UserCRUD(users_db).read_all("students", filter={
    "$or": [
      {"group.en": group},
      {"group.ua": group}
    ]
  })


@router.post("/me/grades",
  status_code=status.HTTP_200_OK,
  operation_id="ReadCurrentUserGrades",
  response_model_exclude_none=True)
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
  return await StudentCRUD(grades_db).get_grades(edbo_id=student.edbo_id, group=student.group.en, subject=grade_body.subject, date=date) 


@router.get("/me/grades/all",
  status_code=status.HTTP_200_OK,
  operation_id="ReadCurrentUserGradesAll")
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
  return await StudentCRUD(grades_db).get_grades(edbo_id=student.edbo_id, group=student.group.en, date=date)


@router.post("/{edbo_id}/grades",
  status_code=status.HTTP_200_OK,
  operation_id="ReadStudentGradesBySubject",
  response_model_exclude_none = True,
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def get_student_grades_by_subject(
  edbo_id: Annotated[int, Path()],
  grade_body: Annotated[GradeBase, Body()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  date: Annotated[str, Query()] = None
):
  """
  Returns all grades for the specified student's subject.
  """
  users_db = mongo.get_database("users")
  student = await StudentCRUD(users_db)._fetch(edbo_id) 

  grades_db = mongo.get_database("grades")
  return await StudentCRUD(grades_db).get_grades(edbo_id=edbo_id, group=student.group.en, subject=grade_body.subject, date=date)


@router.get("/{edbo_id}/grades/all",
  status_code=status.HTTP_200_OK,
  operation_id="ReadtudentGradesAll",
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
  student = await StudentCRUD(users_db)._fetch(edbo_id)

  grades_db = mongo.get_database("grades")
  return await StudentCRUD(grades_db).get_grades(edbo_id=edbo_id, group=student.group.en, date=date)


@router.post("/{group}/assesment/all",
  status_code=status.HTTP_200_OK,
  operation_id="ReadStudentsAllGrades",
  response_model=List[GradeGroup])
async def get_assesment_students(
  group: Annotated[str, Path()],
  discipline: Annotated[str, Body()],
  user: Annotated[dict, Security(get_current_user, scopes=["teacher", "admin"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Returns list of all students grades.
  """
  grades_db = mongo.get_database("grades")
  if group not in await grades_db.list_collection_names():
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Group not found."
    )

  role = user.get("role")
  match role:
    case "teachers":
      teacher = TeacherBase.model_validate(user)
      if discipline not in teacher.disciplines:
        raise HTTPException(
          status_code=status.HTTP_403_FORBIDDEN,
          detail="You don't have access to this discipline."
        )
    case _:
      pass
    
  grades_docs = await BaseCRUD(grades_db).read_all(
    collection=group,
    filter={f"disciplines.{discipline}": {"$exists": True}}
  )

  users_db = mongo.get_database("users")

  filtered_grades_docs = []
  
  grade_doc: dict
  for grade_doc in grades_docs:
    student = await UserCRUD(users_db).find(username=grade_doc.get("edbo_id"))
    if student: grade_doc.update({"student": UserInitial.model_validate(student)}) 

    if "disciplines" in grade_doc:
      original_disciplines: dict = grade_doc.pop("disciplines", {})

      filtered_disciplines = {
        discipline: original_disciplines.get(discipline, {})
      }

      grade_doc["discipline"] = filtered_disciplines

    filtered_grades_docs.append(grade_doc)

  return grades_docs


@router.patch("/{edbo_id}/assessment",
  status_code=status.HTTP_201_CREATED,
  operation_id="AssessStudentByEdboID")
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
  student = await StudentCRUD(users_db)._fetch(edbo_id) 

  if grade_body.subject not in teacher.disciplines:
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="You don't have access to this discipline."
    )
  
  grades_db = mongo.get_database("grades")
  collection = grades_db.get_collection(student.group.en)

  if not (await collection.find_one_and_update(
    filter={"edbo_id": edbo_id},
    update={
      "$set": {f"disciplines.{grade_body.subject}.{grade_body.date}": grade_body.grade},
      "$addToSet": {f"grade_systems.{grade_body.grade_system}": grade_body.subject}}
  )):
    await collection.insert_one(
      {"edbo_id": edbo_id,
       "disciplines": {
         grade_body.subject: {
           grade_body.date: grade_body.grade
         }
       }}
    )
    
  return {"message": "Student successfully assessed."}