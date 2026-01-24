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
from core.schemas.teacher import TeacherBase, TeacherCreate, TeacherGroup
from core.db import MongoClient
from api.dependencies import (
  get_mongo_client,
  get_current_user
)
from api.dependencies import limit_dependency
from crud import UserCRUD, BaseCRUD

router = APIRouter(tags=["Teachers"])

@router.post("",
  status_code=status.HTTP_201_CREATED,
  operation_id="CreateTeacher",
  dependencies=[Security(get_current_user, scopes=["admin"]), Depends(limit_dependency)])
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
  status_code=status.HTTP_200_OK,
  operation_id="ReadAssignedDisicplines",
  dependencies=[Depends(limit_dependency)])
async def get_assigned_disiciplines(
  group: Annotated[str, Path()],
  user: Annotated[dict, Security(get_current_user, scopes=["teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Returns list of assinged disciplines.
  """
  teacher = TeacherBase.model_validate(user)

  query = {"$or": [
    {"group.en": {"$regex": group, "$options": "i"}},
    {"group.ua": {"$regex": group, "$options": "i"}}
  ]}
  groups_db = mongo.get_database("groups")  
  for degree in await groups_db.list_collection_names():
    if (student_group := await BaseCRUD(groups_db).read(degree, filter=query)):
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
  operation_id="ReadAssignedGroups",
  response_model=Dict[str, List[TeacherGroup]],
  dependencies=[Depends(limit_dependency)])
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
        "class_teacher_edbo": teacher.edbo_id  
      }
    )
    groups.update({degree: group_list})
  
  return groups