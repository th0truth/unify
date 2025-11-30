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
from core.schemas.user import UserBase
from core.schemas.student import StudentBase
from core.schemas.teacher import TeacherBase
from core.schemas.group import GroupBase, GroupCreate
from core.db import MongoClient
from api.dependencies import (
  get_mongo_client,
  get_current_user
)

router = APIRouter(tags=["Groups"])

async def get_detail_disciplines(mongo: MongoClient, *, group: dict) -> dict:
  users_db = mongo.get_database("users")
  collection = users_db.get_collection("teachers")
  group.update(
    {"disciplines": [{
      discipline: UserBase.model_validate(
        await collection.find_one({"edbo_id": edbo_id}))} for discipline, edbo_id in group["disciplines"].items()]
    }
  )
  return group


@router.post("",
  status_code=status.HTTP_201_CREATED,
  response_model=GroupCreate,
  dependencies=[Security(get_current_user, scopes=["admin"])])
async def create_group(
  create_group: Annotated[GroupCreate, Body()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Creates the student group.
  """
  groups_db = mongo.get_database("groups")
  collections = await groups_db.list_collection_names()
  if create_group.degree not in collections:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Group degree not found."
    )
  
  for degree in collections:
    collection = groups_db.get_collection(degree)
    if await collection.find_one({"group.ua": create_group.group.ua}):
      raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Group already exits."
      )
  
  await collection.insert_one(
    create_group.model_dump()
  )
  
  return create_group


@router.get("/my",
  status_code=status.HTTP_200_OK,
  response_model=GroupBase)
async def get_current_user_group(
  user: Annotated[dict, Security(get_current_user, scopes=["student", "teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Returns the student group.  
  """
  groups_db = mongo.get_database("groups")
  role = user.get("role")
  match role:
    case "students":
      student = StudentBase.model_validate(user)
      for degree in await groups_db.list_collection_names():
        collection = groups_db.get_collection(degree)
        if (group := await collection.find_one({"group.ua": student.group.ua})):
          break

    case "teachers":
      teacher = TeacherBase.model_validate(user)
      for degree in await groups_db.list_collection_names():
        collection = groups_db.get_collection(degree)
        if (group := await collection.find_one({"class_teacher_edbo": teacher.edbo_id})):
          break

  if not group:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Group not found"
    )
  
  group = await get_detail_disciplines(mongo, group=group)
  return group


@router.get("/all",
  status_code=status.HTTP_200_OK,
  response_model=Dict[str, List[GroupBase]],
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def read_groups(
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Returns all student groups. 
  """
  
  groups = {}
  groups_db = mongo.get_database("groups")
  for degree in await groups_db.list_collection_names():
    collection = groups_db.get_collection(degree)
    group_list = await collection.find().to_list()
    groups.update({degree: group_list})
  
  return groups

@router.get("/{group}",
  status_code=status.HTTP_200_OK,
  response_model=GroupBase,
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def get_group(
  group: Annotated[str, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Returns the group by `name`.
  """
  groups_db = mongo.get_database("groups")
  for degree in await groups_db.list_collection_names():
    collection = groups_db.get_collection(degree)
    if (student_group := await collection.find_one({"group.ua": group})):
      break
  if not student_group:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Group not found."
    )
  
  student_group = await get_detail_disciplines(mongo, group=student_group)
  return student_group
 

@router.delete("/{group}",
  dependencies=[Security(get_current_user, scopes=["admin"])])
async def delete_group(
  group: Annotated[str, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Deletes the student group.
  """
  groups_db = mongo.get_database("groups") 
  for degree in await groups_db.list_collection_names():
    collection = groups_db.get_collection(degree)
    if (student_group := await collection.find_one({"group.ua": group})):
      break
  if not student_group:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Group not found."
    )
  
  await collection.delete_one(student_group)

  return {"message": "The group has been deleted."}