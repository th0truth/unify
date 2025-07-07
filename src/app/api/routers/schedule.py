from typing import Annotated, List
from fastapi import (
  HTTPException,
  APIRouter,
  status,
  Security,
  Depends,
  Path,
  Body
)
import uuid
from core.schemas.schedule import (
  ScheduleBase,
  ScheduleCreate,
  SchedulePrivate
)
from core.schemas.user import UserBase
from core.schemas.student import StudentBase
from core.schemas.teacher import TeacherBase
from core.db import MongoClient
from api.dependencies import (
  get_mongo_client,
  get_current_user
)
import crud

router = APIRouter(tags=["Schedule"])

@router.get("/my",
  status_code=status.HTTP_200_OK,
  response_model=list[SchedulePrivate],
  response_model_exclude_none=True)
async def get_current_user_schedule(
  user: Annotated[dict, Security(get_current_user, scopes=["student", "teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Returns the schedule for the current user. 
  """
  schedule_db = mongo.get_database("schedule")
  match user.get("role"):
    case "students":
      student = StudentBase.model_validate(user) 
      collection = schedule_db.get_collection(student.group)
      schedule = await collection.find().to_list()

      grades_db = mongo.get_database("grades")
      grades_doc = await crud.get_grades(grades_db, edbo_id=student.edbo_id, group=student.group)
      
      users_db = mongo.get_database("users")
      collection = users_db.get_collection("teachers")
      for lesson in schedule:
        teacher = await collection.find_one({"edbo_id": lesson.pop("teacher_edbo")})
        lesson.update(
          {"teacher": TeacherBase.model_validate(teacher).model_dump(),
           "grade": grades_doc.get(lesson["subject"], {}).get(lesson["date"])})
      return schedule

    case "teachers":
      teacher = UserBase.model_validate(user)
      for group in await schedule_db.list_collection_names():
        collection = schedule_db.get_collection(group)
        schedule = await collection.find({"teacher_edbo": teacher.edbo_id}).to_list()
        for lesson in schedule:
          lesson.update({"teacher": teacher})
      return schedule

@router.get("/{group}",
  status_code=status.HTTP_200_OK,
  response_model=List[SchedulePrivate],
  response_model_exclude_none=True,
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def get_schedule_by_group(
  group: Annotated[str, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Returns the schedule with the given `group`. 
  """
  schedule_db = mongo.get_database("schedule")
  collection = schedule_db.get_collection(group)
  schedule = await collection.find().to_list()
  return schedule

@router.get("/{group}/{id}", 
  status_code=status.HTTP_200_OK,
  response_model=SchedulePrivate,
  response_model_exclude_none=True,
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def get_schedule_by_id(
  group: Annotated[str, Path()],
  id: Annotated[str, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Returns the schedule with the given `id`.
  """
  schedule_db = mongo.get_database("schedule")
  collection = schedule_db.get_collection(group)
  if group not in await schedule_db.list_collection_names():
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Given group not found."
    )

  if not (lesson := await collection.find_one({"lesson_id": id})):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Lesson not found."
    )
  return lesson

@router.post("/create",
  status_code=status.HTTP_201_CREATED,
  response_model=ScheduleBase)
async def create_schedule(
  schedule: Annotated[ScheduleCreate, Body()],
  user: Annotated[dict, Security(get_current_user, scopes=["teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
):
  """
  Creates a schedule.
  """
  teacher = TeacherBase.model_validate(user)

  if schedule.subject not in teacher.disciplines:
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="You don't have access to this discipline."
    )

  groups_db = mongo.get_database("groups")
  for degree in await groups_db.list_collection_names():
    collection = groups_db.get_collection(degree)
    if (group := await collection.find_one({"group": schedule.group})):
      break
  if not group:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Given group not found."
    )
  
  schedule_db = mongo.get_database("schedule")
  collection = schedule_db.get_collection(schedule.group)
  
  schedule_private = SchedulePrivate(
    **schedule.model_dump(),
    teacher_edbo=teacher.edbo_id,
    lesson_id=str(uuid.uuid4())
  )

  await collection.insert_one(
    schedule_private.model_dump(exclude_none=True)
  )

  return schedule

@router.put("/{group}/{id}/update",
  status_code=status.HTTP_200_OK,
  response_model=ScheduleBase)
async def update_schedule(
  group: Annotated[str, Path()],
  id: Annotated[str, Path()],
  schedule_update: Annotated[ScheduleBase, Body()],
  user: Annotated[MongoClient, Security(get_current_user, scopes=["teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Updates the lesson specified by `id`.
  """
  teacher = TeacherBase.model_validate(user)

  schedule_db = mongo.get_database("schedule")
  if schedule_update.subject not in teacher.disciplines:
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="You don't have access to this discipline."
    )

  if group not in await schedule_db.list_collection_names():
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Given group not found."
    )

  collection = schedule_db.get_collection(group)
  lesson = await collection.find_one_and_update(
    {"lesson_id": id}, {"$set": schedule_update.model_dump()})
  if not lesson:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Lesson not found."
    )
  
  return schedule_update

@router.delete("/{group}/{id}/delete",
  status_code=status.HTTP_200_OK,
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def delete_schedule(
  group: Annotated[str, Path()],
  id: Annotated[str, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Deletes the lesson specified by `id`.
  """
  
  schedule_db = mongo.get_database("schedule")
  
  if group not in await schedule_db.list_collection_names():
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Given group not found."
    )

  collection = schedule_db.get_collection(group)
  if not await collection.find_one_and_delete({"lesson_id": id}):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Lesson not found."
    )
  
  raise HTTPException(
    status_code=status.HTTP_200_OK,
    detail="The lesson has been deleted."
  )