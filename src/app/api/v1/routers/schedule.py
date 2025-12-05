from typing import Annotated, List
import cloudinary.exceptions
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
from datetime import timedelta
import cloudinary
import json
import uuid

from core.logger import logger
from core.config import settings

from core.security.utils import convert_size
from core.schemas.schedule import (
  ScheduleBase,
  ScheduleCreate,
  ScheduleUpdate,
  SchedulePrivate
)
from core.schemas.user import UserInitial, UserBase
from core.schemas.student import StudentBase
from core.schemas.teacher import TeacherBase
from core.schemas.etc import MetaFile
from core.db import MongoClient
from redis.asyncio import Redis
from api.dependencies import (
  get_mongo_client,
  get_redis_client,
  get_current_user
)
from crud import StudentCRUD

router = APIRouter(tags=["Schedule"])

cloudinary.config(
  cloud_name=settings.CLOUDINARY_CLOUD_NAME,
  api_key=settings.CLOUDINARY_API_KEY,
  api_secret=settings.CLOUDINARY_API_SECRET,
  secure=True
)

@router.post("",
  status_code=status.HTTP_201_CREATED,
  operation_id="CreateSchedule",
  response_model=ScheduleBase)
async def create_schedule(
  schedule: Annotated[ScheduleCreate, Body()],
  user: Annotated[dict, Security(get_current_user, scopes=["teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  redis: Annotated[Redis, Depends(get_redis_client)]
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
    if (group := await groups_db[degree].find_one(
      {"$or": [
        {"group.en": schedule.group.en},
        {"group.ua": schedule.group.ua}
      ]}
    )):
      break
  if not group:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Given group not found."
    )

  schedule_private = SchedulePrivate(
    **schedule.model_dump(),
    teacher_edbo=teacher.edbo_id,
    lesson_id=str(uuid.uuid4().hex)
  )

  # Insert the schedule to the MongoDB database
  schedule_db = mongo.get_database("schedule")
  await schedule_db[schedule.group.en].insert_one(
    schedule_private.model_dump(exclude_none=True)
  )

  await redis.delete(f"cache:groups:{schedule.group.en}:schedule")
  await redis.delete(f"cache:user:{teacher.edbo_id}:schedule")

  return schedule


@router.get("/me",
  status_code=status.HTTP_200_OK,
  operation_id="ReadCurrentUserSchedule",
  response_model=List[SchedulePrivate],
  response_model_exclude_none=True)
async def get_current_user_schedule(
  user: Annotated[dict, Security(get_current_user, scopes=["student", "teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  redis: Annotated[Redis, Depends(get_redis_client)]
):
  """
  Returns the schedule for the current user. 
  """
  schedule_db = mongo.get_database("schedule")
  role = user.get("role")
  match role:
    case "students":
      student = StudentBase.model_validate(user) 
 
      redis_key = f"cache:groups:{student.group.en}:schedule"

      try:
        # Check if student schedule exits in Redis cache
        if (schedule_cache := await redis.get(redis_key)):
          try:
            return json.loads(schedule_cache)
          except json.JSONDecodeError:
            logger.error({"message": "[x] Failed decode schedule from Redis cache.", "detail": str(err)}, exc_info=True)
      
        # Find schedule in MongoDB
        schedule = await schedule_db[student.group.en].find().to_list()

        # Get grades
        grades_db = mongo.get_database("grades")
        grades_doc = await StudentCRUD(grades_db).get_grades(edbo_id=student.edbo_id, group=student.group.en)

        lesson: dict
        users_db = mongo.get_database("users")
        for lesson in schedule:
          teacher = await users_db["teachers"].find_one({"edbo_id": lesson.pop("teacher_edbo")})
          updated_lesson = {
            **lesson,
            "teacher": UserInitial.model_validate(teacher),
            "grade": grades_doc.get(lesson.get("subject"), {}).get(lesson.get("date"))
          }
          lesson.clear()
          lesson.update(SchedulePrivate.model_validate(updated_lesson).model_dump())

        # Store student schedule in Redis cache
        await redis.setex(redis_key, timedelta(minutes=settings.CACHE_EXPIRE_MINUTES).seconds, json.dumps(schedule, default=str))
        
        return schedule
      
      except Exception as err:
        logger.error({"detail": str(err)}, exc_info=True)
        raise HTTPException(
          status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
          detail="Internal server error."
        )
    case "teachers":
      teacher = UserBase.model_validate(user)

      redis_key = f"cache:user:{teacher.edbo_id}:schedule"
      
      if (schedule_cache := await redis.get(redis_key)):
        try:
          return json.loads(schedule_cache)
        except json.JSONDecodeError:
          logger.error({"message": "[x] Failed decode schedule from Redis cache.", "detail": str(err)}, exc_info=True)

      schedule_list = []
      for group in await schedule_db.list_collection_names():
        schedule = await schedule_db[group].find({"teacher_edbo": teacher.edbo_id}).to_list()
        for lesson in schedule:
          lesson.update({"teacher": UserInitial.model_validate(teacher)})
          schedule_list.append(lesson)
      
      # Store student schedule in Redis cache
      await redis.setex(redis_key, timedelta(minutes=settings.CACHE_EXPIRE_MINUTES).seconds, json.dumps(schedule, default=str))
      
      return schedule_list


@router.get("/{group}",
  status_code=status.HTTP_200_OK,
  operation_id="ReadScheduleByGroupName",
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
  schedule = await schedule_db[group].find().to_list()
  return schedule


@router.get("/{group}/{lesson_id}/details", 
  status_code=status.HTTP_200_OK,
  operation_id="ReadScheduleLessonById",
  response_model=SchedulePrivate,
  response_model_exclude_none=True,
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def get_schedule_by_id(
  group: Annotated[str, Path()],
  lesson_id: Annotated[str, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Returns the schedule with the given `lesson_id`.
  """
  schedule_db = mongo.get_database("schedule")
  if group not in await schedule_db.list_collection_names():
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Given group not found."
    )

  if not (schedule_lesson := await schedule_db[group].find_one({"lesson_id": lesson_id})):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Lesson not found."
    )
  return schedule_lesson


@router.put("/{group}/{lesson_id}/revision",
  status_code=status.HTTP_200_OK,
  operation_id="UpdateScheduleLesson")
async def update_schedule_lesson(
  group: Annotated[str, Path()],
  lesson_id: Annotated[str, Path()],
  schedule_update: Annotated[ScheduleUpdate, Body()],
  user: Annotated[MongoClient, Security(get_current_user, scopes=["teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Updates the lesson specified by `lesson_id`.
  """
  teacher = TeacherBase.model_validate(user)

  schedule_db = mongo.get_database("schedule")
  if schedule_update.subject and schedule_update.subject not in teacher.disciplines:
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="You don't have access to this discipline."
    )

  if group not in await schedule_db.list_collection_names():
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Given group not found."
    )

  lesson = await schedule_db[group].find_one_and_update(
    filter={"lesson_id": lesson_id},
    update={"$set": schedule_update.model_dump(exclude_unset=True)}
  )
  if not lesson:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Lesson not found."
    )
  
  return {"message": "The lesson has been successfully updated."}


@router.delete("/{group}/{lesson_id}",
  status_code=status.HTTP_204_NO_CONTENT,
  operation_id="DeleteScheduleLessonById",
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def delete_schedule_lesson(
  group: Annotated[str, Path()],
  lesson_id: Annotated[str, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Deletes the lesson specified by `lesson_id`.
  """
  
  schedule_db = mongo.get_database("schedule")
  
  if group not in await schedule_db.list_collection_names():
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Given group not found."
    )

  if not await schedule_db[group].find_one_and_delete({"lesson_id": lesson_id}):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Lesson not found."
    )
  
  return {"message": "The lesson has been deleted."}


@router.post("/{group}/{lesson_id}/attachment",
  status_code=status.HTTP_200_OK,
  operation_id="AttachScheduleFiles",
  response_model=List[MetaFile],
  response_model_exclude_none=True)
async def upload_schedule_files(
  group: Annotated[str, Path()],
  lesson_id: Annotated[str, Path()],
  files: Annotated[List[UploadFile], File()],
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
  
  if not (lesson := await schedule_db[group].find_one(
    filter={"teacher_edbo": teacher.edbo_id, "lesson_id": lesson_id})):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Lesson not found."
    ) 

  attachments = []
  for file in files: 
    try:
      # Upload to Cloudinary
      filename = file.filename
      file_content = await file.read()
      upload_result = cloudinary.uploader.upload(
        file=file_content,
        display_name=filename,
        asset_folder="schedule",
        resource_type="auto",
        use_filename=False,
        unique_filename=True
      )
      # Append upload result to list
      attachments.append(
        MetaFile(
          metadata={
            "filename": filename,
            "width": upload_result["width"],
            "height": upload_result["height"],
            "format": upload_result["format"],
            "created": upload_result["created_at"],
            "bytes": convert_size(upload_result["bytes"]),
          },
          url=upload_result["secure_url"],
          file_id=upload_result["public_id"],
          file_type=upload_result["resource_type"],
          group=group,
          lesson_id=lesson_id
        ).model_dump()
      )
    except cloudinary.exceptions.Error as err:
      logger.error(
        {"msg": "[x] An error occured while attaching files to the lesson.",
         "erorr": err
        })
      raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Error attaching files."
      )
  
  if not (await schedule_db[group].update_one(
    filter=lesson,
    update={"$push": {"attachments": {"$each": attachments}}})
  ):
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="Can't attachment your files to the lesson."
    ) 
  
  return attachments


@router.post("/{group}/{lesson_id}/attachment/{file_id}",
  status_code=status.HTTP_200_OK,
  operation_id="DetachScheduleFile")
async def detach_schedule_file(
  group: Annotated[str, Path()],
  lesson_id: Annotated[str, Path()],
  file_id: Annotated[str, Path()],
  user: Annotated[dict, Security(get_current_user, scopes=["teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Detaches the file from the lesson.
  """
  teacher = TeacherBase.model_validate(user)

  schedule_db = mongo.get_database("schedule")
  if group not in await schedule_db.list_collection_names():
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Group not found."
    )
  
  if not (schedule_lesson := await schedule_db[group].find_one(
    filter={
      "teacher_edbo": teacher.edbo_id,
      "lesson_id": lesson_id,
      "attachments": {"$elemMatch": {"file_id": file_id}},
    })):
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Lesson not found."
      ) 
  for attachment in schedule_lesson["attachments"]:
    if (file_id == attachment["file_id"]):
      file_type = attachment["file_type"]
  try:
    detach_result = cloudinary.uploader.destroy(
      public_id=file_id,
      resource_type=file_type
    )
  except cloudinary.exceptions.Error as err:
    logger.error(
    {"msg": "[x] An error occured while detaching files from the lesson.",
     "erorr": err
    })
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="An error occured while detaching the file."
    )

  if detach_result != "ok":
    HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="File not found in the cloud."
    )  

  await schedule_db[group].update_one(
    filter=schedule_lesson,
    update={"$pull": {"attachments": {"file_id": file_id}}}
  )

  return {"message": "The file has been successfully detached."}