from typing import Annotated, List, Union, Optional
import cloudinary.uploader
from fastapi import (
  HTTPException,
  APIRouter,
  status,
  UploadFile,
  File,
  Security,
  Depends,
  Path,
  Body
)
import uuid
import cloudinary

from core.config import settings
from core.security.utils import convert_size
from core.schemas.schedule import (
  ScheduleBase,
  ScheduleCreate,
  SchedulePrivate,
  ScheduleFile
)
from core.schemas.user import UserInitial, UserBase
from core.schemas.student import StudentBase
from core.schemas.teacher import TeacherBase
from core.db import MongoClient
from api.dependencies import (
  get_mongo_client,
  get_current_user
)
import crud

router = APIRouter(tags=["Schedule"])

cloudinary.config(
  cloud_name=settings.CLOUDINARY_CLOUD_NAME,
  api_key=settings.CLOUDINARY_API_KEY,
  api_secret=settings.CLOUDINARY_API_SECRET,
  secure=True
)

@router.get("/my",
  status_code=status.HTTP_200_OK,
  response_model=List[SchedulePrivate],
  response_model_exclude_none=True)
async def get_current_user_schedule(
  user: Annotated[dict, Security(get_current_user, scopes=["student", "teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Returns the schedule for the current user. 
  """
  schedule_db = mongo.get_database("schedule")
  role = user.get("role")
  match role:
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
          {"teacher": UserInitial.model_validate(teacher),
           "grade": grades_doc.get(lesson["subject"], {}).get(lesson["date"])})
      return schedule

    case "teachers":
      teacher = UserBase.model_validate(user)
      for group in await schedule_db.list_collection_names():
        collection = schedule_db.get_collection(group)
        schedule = await collection.find({"teacher_edbo": teacher.edbo_id}).to_list()
        for lesson in schedule:
          lesson.update({"teacher": UserInitial.model_validate(teacher)})
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

  # Check if the teacher's subject is matches the discipline.
  if schedule.subject not in teacher.disciplines:
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="You don't have access to this discipline."
    )

  # Find out the specified group.
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

  schedule_private = SchedulePrivate(
    **schedule.model_dump(),
    teacher_edbo=teacher.edbo_id,
    lesson_id=str(uuid.uuid4())
  )

  # Insert the schedule to the MongoDB database
  schedule_db = mongo.get_database("schedule")
  collection = schedule_db.get_collection(schedule.group)
  await collection.insert_one(
    schedule_private.model_dump(exclude_none=True)
  )

  return schedule

@router.post("/{group}/{id}/attach",
  status_code=status.HTTP_200_OK,
  response_model=SchedulePrivate,
  response_model_exclude_none=True)
async def upload_schedule_files(
  group: Annotated[str, Path()],
  id: Annotated[str, Path()],
  files: Annotated[List[UploadFile], File(...)],
  user: Annotated[dict, Security(get_current_user, scopes=["teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Attaches files to the lesson.
  """
  teacher = TeacherBase.model_validate(user)

  schedule_db = mongo.get_database("schedule")
  if group not in await schedule_db.list_collection_names():
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Group not found."
    )
  
  collection = schedule_db.get_collection(group)
  if not (lesson := await collection.find_one(
    filter={"teacher_edbo": teacher.edbo_id, "lesson_id": id})):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Lesson not found."
    ) 

  response_content = []
  for file in files: 
    try:
      # Upload to Cloudinary
      filename = file.filename
      file_content = await file.read()
      upload_result = cloudinary.uploader.upload(
        file=file_content,
        display_name=filename,
        asset_folder="schedule"
      )
      # Append upload result to list
      response_content.append(
        ScheduleFile(
          metadata={
            "filename": filename,
            "width": upload_result["width"],
            "height": upload_result["height"],
            "format": upload_result["format"],
            "created": upload_result["created_at"],
            "bytes": convert_size(upload_result["bytes"]),
          },
          url=upload_result["secure_url"],
          group=group,
          lesson_id=id
        ).model_dump()
      )
    except:
      raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Error attaching files."
      )
  
  if not (await collection.update_one(
    filter=lesson,
    update={"$set": {"attachments": response_content}})
  ):
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="Can't attachment your files to the lesson."
    ) 
  return lesson

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
    filter={"lesson_id": id},
    update={"$set": schedule_update.model_dump()}
  )
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