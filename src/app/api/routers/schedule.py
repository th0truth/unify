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
import uuid
import cloudinary

from core.logger import logger
from core.config import settings
from core.security.utils import convert_size
from core.schemas.schedule import (
  ScheduleBase,
  ScheduleCreate,
  SchedulePrivate
)
from core.schemas.user import UserInitial, UserBase
from core.schemas.student import StudentBase
from core.schemas.teacher import TeacherBase
from core.schemas.etc import MetaFile
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
      collection = schedule_db.get_collection(student.group.en)
      schedule = await collection.find().to_list()

      grades_db = mongo.get_database("grades")
      grades_doc = await crud.get_grades(grades_db, edbo_id=student.edbo_id, group=student.group.en)
      
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

@router.get("/{group}/{lesson_id}", 
  status_code=status.HTTP_200_OK,
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
  collection = schedule_db.get_collection(group)
  if group not in await schedule_db.list_collection_names():
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Given group not found."
    )

  if not (schedule_lesson := await collection.find_one({"lesson_id": lesson_id})):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Lesson not found."
    )
  return schedule_lesson

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
    if (group := await collection.find_one({"group.en": schedule.group.en})):
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
  collection = schedule_db.get_collection(schedule.group.en)
  await collection.insert_one(
    schedule_private.model_dump(exclude_none=True)
  )

  return schedule

@router.post("/{group}/{lesson_id}/attach",
  status_code=status.HTTP_200_OK,
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
  
  collection = schedule_db.get_collection(group)
  if not (lesson := await collection.find_one(
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
  
  if not (await collection.update_one(
    filter=lesson,
    update={"$push": {"attachments": {"$each": attachments}}})
  ):
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="Can't attachment your files to the lesson."
    ) 
  
  return attachments

@router.post("/{group}/{lesson_id}/detach/{file_id}",
  status_code=status.HTTP_200_OK)
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
  
  collection = schedule_db.get_collection(group)
  if not (schedule_lesson := await collection.find_one(
    filter={
      "teacher_edbo": teacher.edbo_id,
      "lesson_id": lesson_id,
      "attachments": {"$elemMatch": {"file_id": file_id}},
    })):
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Not found."
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

  await collection.update_one(
    filter=schedule_lesson,
    update={"$pull": {"attachments": {"file_id": file_id}}}
  )

  return {"message": "File detached successfully."}

@router.put("/{group}/{lesson_id}/update",
  status_code=status.HTTP_200_OK,
  response_model=ScheduleBase)
async def update_schedule(
  group: Annotated[str, Path()],
  lesson_id: Annotated[str, Path()],
  schedule_update: Annotated[ScheduleBase, Body()],
  user: Annotated[MongoClient, Security(get_current_user, scopes=["teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Updates the lesson specified by `lesson_id`.
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
    filter={"lesson_id": lesson_id},
    update={"$set": schedule_update.model_dump()}
  )
  if not lesson:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Lesson not found."
    )
  
  return schedule_update

@router.delete("/{group}/{lesson_id}/delete",
  status_code=status.HTTP_200_OK,
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def delete_schedule(
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

  collection = schedule_db.get_collection(group)
  if not await collection.find_one_and_delete({"lesson_id": lesson_id}):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Lesson not found."
    )
  
  return {"message": "The lesson has been deleted."}