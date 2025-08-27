from typing import Annotated, Dict, List
from fastapi import (
  HTTPException,
  APIRouter,
  status,
  Security,
  Depends,
  Path,
  Body
)
from core.schemas.group import GroupBase
from core.schemas.student import StudentBase
from core.schemas.teacher import TeacherBase, TeacherCreate, TeacherGroup
from core.schemas.grade import SetGrade, GradeGroup
from core.db import MongoClient
from api.dependencies import (
  get_mongo_client,
  get_current_user
)
from crud import UserCRUD, BaseCRUD

router = APIRouter(tags=["Teachers"])

@router.post("/create",
  status_code=status.HTTP_201_CREATED,
  dependencies=[Security(get_current_user, scopes=["admin"])])
async def create_teacher(
  create_teacher: Annotated[TeacherCreate, Body()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Creates a teacher account.
  """
  # Check if the user already exists
  users_db = mongo.get_database("users")
  if await UserCRUD(users_db).find(username=create_teacher.edbo_id):
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail="User already exists."
    )
  
  # Create a teacher account
  await UserCRUD(users_db).create(create_teacher)  

  return {"message": "The teacher account was created successfully."}

@router.get("/assigned/{group}/disciplines",
  response_model=List,
  status_code=status.HTTP_200_OK)
async def get_assigned_disicplines(
  group: Annotated[str, Path()],
  user: Annotated[dict, Security(get_current_user, scopes=["teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Returns list of assinged disciplines.
  """
  teacher = TeacherBase.model_validate(user)

  groups_db = mongo.get_database("groups")
  for degree in await groups_db.list_collection_names():
    if (student_group := await BaseCRUD(groups_db).read(degree, filter={"group.en": group})):
      break
  if not student_group: 
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Group not found."
    )
  
  student_group = GroupBase.model_validate(student_group)
  
  disciplines = []
  for discipline in student_group.disciplines:
    if discipline in teacher.disciplines:
      disciplines.append(discipline)

  return disciplines

@router.get("/assigned/groups",
  status_code=status.HTTP_200_OK,
  response_model=Dict[str, List[TeacherGroup]])
async def get_assigned_groups(
  user: Annotated[dict, Security(get_current_user, scopes=["teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Returns assigned groups for the teacher.
  """
  teacher = TeacherBase.model_validate(user)

  groups = {}
  groups_db = mongo.get_database("groups")
  for degree in await groups_db.list_collection_names():
    group_list = await BaseCRUD(groups_db).read_all(
      collection=degree,
      filter={
        "$expr": {
        "$in": [
            teacher.edbo_id,
            {"$map": {"input": {"$objectToArray": "$disciplines"}, "as": "d", "in": "$$d.v"}}
          ]
        }
      }
    )
    groups.update({degree: group_list})
  
  return groups

@router.post("/assesment/{group}/all",
  status_code=status.HTTP_200_OK,
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
    
  grades = await BaseCRUD(grades_db).read_all(
    group,
    filter={f"disciplines.{discipline}": {"$exists": True}},
    projection={"edbo_id": 1, f"disciplines.{discipline}": 1}
  )

  return grades

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
  collection = grades_db.get_collection(student.group.en)

  if not (await collection.find_one_and_update(
    filter={"edbo_id": edbo_id},
    update={"$set": {f"disciplines.{grade_body.subject}.{grade_body.date}": grade_body.grade}}
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