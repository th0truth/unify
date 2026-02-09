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
from core.database import MongoClient
from api.dependencies import (
  get_mongo_client,
  get_current_user
)
from api.dependencies import limit_dependency

router = APIRouter(tags=["Groups"])


async def get_detail_disciplines(mongo: MongoClient, *, group: dict) -> dict:
  users_db = mongo.get_database("users")
  group.update(
    {"disciplines": [{
      discipline: UserBase.model_validate(
        await users_db["teachers"].find_one({"edbo_id": edbo_id}))} for discipline, edbo_id in group["disciplines"].items()]
    }
  )
  return group


@router.post("",
  status_code=status.HTTP_201_CREATED,
  operation_id="CreateGroup",
  response_model=GroupCreate,
  dependencies=[
    Security(get_current_user, scopes=["admin"]),
    Depends(limit_dependency)])
async def create_group(
  group_data: Annotated[GroupCreate, Body()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Creates the student group.
  """
  groups_db = mongo.get_database("groups")
  degrees = await groups_db.list_collection_names()
  if group_data.degree not in degrees:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Group degree not found."
    )
  
  for degree in degrees:
    if await groups_db[degree].find_one(
      {"$or": [
        {"group.en": group_data.group.en},
        {"group.ua": group_data.group.ua}
      ]}
    ):
      raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Group already exits."
      )
  
  await groups_db[degree].insert_one(
    group_data.model_dump()
  )
  
  return group_data


@router.get("/me",
  status_code=status.HTTP_200_OK,
  operation_id="ReadCurrentUserGroup",
  response_model=GroupBase,
  dependencies=[
    Depends(limit_dependency)])
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
        if (group := await groups_db[degree].find_one(
          {"$or": [
            {"group.en": student.group.en},
            {"group.ua": student.group.ua}
          ]}
        )):
          break

    case "teachers":
      teacher = TeacherBase.model_validate(user)
      for degree in await groups_db.list_collection_names():
        if (group := await groups_db[degree].find_one({"class_teacher_edbo": teacher.edbo_id})):
          break

  if not group:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Group not found"
    )
  
  return await get_detail_disciplines(mongo, group=group)


@router.get("/all",
  status_code=status.HTTP_200_OK,
  operation_id="ReadAllGroups",
  response_model=Dict[str, List[GroupBase]],
  dependencies=[
    Security(get_current_user, scopes=["teacher", "admin"]),
    Depends(limit_dependency)])
async def get_groups(
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Returns all student groups. 
  """
  
  groups = {}
  groups_db = mongo.get_database("groups")
  for degree in await groups_db.list_collection_names():
    group_list = await groups_db[degree].find().to_list()
    groups.update({degree: group_list})
  
  return groups

@router.get("/{group}",
  status_code=status.HTTP_200_OK,
  operation_id="ReadGroupByName",
  response_model=GroupBase,
  dependencies=[
    Security(get_current_user, scopes=["teacher", "admin"]),
    Depends(limit_dependency)])
async def get_group(
  group: Annotated[str, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Returns the group by `name`.
  """
  groups_db = mongo.get_database("groups")
  for degree in await groups_db.list_collection_names():
    if (student_group := await groups_db[degree].find_one(
      {"$or": [
        {"group.en": group},
        {"group.ua": group}
      ]}
    )):
      break
  if not student_group:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Group not found."
    )
  
  return await get_detail_disciplines(mongo, group=student_group)
 

@router.delete("/{group}",
  status_code=status.HTTP_204_NO_CONTENT,
  operation_id="DeleteGroupByName",
  dependencies=[
    Security(get_current_user, scopes=["admin"]),
    Depends(limit_dependency)])
async def delete_group(
  group: Annotated[str, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Deletes the student group.
  """
  groups_db = mongo.get_database("groups") 
  for degree in await groups_db.list_collection_names():
    if (student_group := await groups_db[degree].find_one(
      {"$or": [
        {"group.en": group},
        {"group.ua": group}
      ]}
    )):
      break
  if not student_group:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Group not found."
    )
  
  await groups_db[degree].delete_one(student_group)

  return {"message": "The group has been deleted."}
