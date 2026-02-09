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
import cloudinary
import uuid

from core.logger import logger
from core.config import settings

from core.security.utils import convert_size
from core.schemas.schedule import (
  ScheduleCreate,
  ScheduleUpdate,
  SchedulePrivate
)
from core.schemas.user import UserInitial, UserBase
from core.schemas.student import StudentBase
from core.schemas.teacher import TeacherBase
from core.schemas.etc import MetaFile
from core.database import MongoClient
from api.dependencies import get_mongo_client, get_current_user
from api.dependencies import limit_dependency
from crud import StudentCRUD

router = APIRouter(tags=["Schedule"])

cloudinary.config(
  cloud_name=settings.CLOUDINARY_CLOUD_NAME,
  api_key=settings.CLOUDINARY_API_KEY,
  api_secret=settings.CLOUDINARY_API_SECRET,
  secure=True,
)


@router.post("",
  status_code=status.HTTP_201_CREATED,
  operation_id="CreateLesson",
  response_model=SchedulePrivate,
  dependencies=[
    Depends(limit_dependency)])
async def create_lesson(
  schedule: Annotated[ScheduleCreate, Body()],
  user: Annotated[dict, Security(get_current_user, scopes=["teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
):
  """
  Create a new lesson.
  """
  teacher = TeacherBase.model_validate(user)

  # Check if teacher's subject matches the discipline.
  if schedule.subject not in teacher.disciplines:
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="You don't have access to this discipline.",
    )
  
  # Find out the specified group.
  groups_db = mongo.get_database("groups")
  group_found = None
  for degree in await groups_db.list_collection_names():
    if group_found := await groups_db[degree].find_one({"group.en": schedule.group.en}):
      break

  if not group_found:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND, detail="Group not found."
    )

  schedule_private = SchedulePrivate(
    **schedule.model_dump(),
    teacher_edbo=teacher.edbo_id,
    lesson_id=str(uuid.uuid4().hex),
  )

  # Insert the lesson to the MongoDB database
  schedule_db = mongo.get_database("schedule")
  await schedule_db["lessons"].insert_one(
    schedule_private.model_dump(mode="python", exclude_none=True)
  )

  return schedule_private


@router.get("/me",
  status_code=status.HTTP_200_OK,
  operation_id="GetMySchedule",
  response_model=List[SchedulePrivate],
  response_model_exclude_none=True,
  dependencies=[
    Depends(limit_dependency)])
async def get_my_schedule(
  user: Annotated[dict, Security(get_current_user, scopes=["student", "teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
):
  """
  Get user's schedule.
  """
  schedule_db = mongo.get_database("schedule")
  role = user.get("role")

  match role:
    case "students":
      student = StudentBase.model_validate(user)

      try:
        # Find schedule in MongoDB
        schedule = await schedule_db["lessons"].find({"group.en": student.group.en}).to_list()

        # Get grades
        grades_db = mongo.get_database("grades")
        grades_doc = await StudentCRUD(grades_db).get_grades(
          edbo_id=student.edbo_id, group=student.group.en
        )
      
        lesson = {}
        users_db = mongo.get_database("users")
        for lesson in schedule:
          teacher_doc = await users_db["teachers"].find_one({"edbo_id": lesson.pop("teacher_edbo")})
          updated_lesson = {
            **lesson,
            "teacher": UserInitial.model_validate(teacher_doc).model_dump(),
            "grade": grades_doc.get(lesson.get("subject"), {}).get("grades", {}).get(lesson.get("date"))
          }
          lesson.clear()
          lesson.update(SchedulePrivate.model_validate(updated_lesson).model_dump())

        return schedule

      except Exception as err:
        logger.error({"detail": str(err)}, exc_info=True)
        raise HTTPException(
          status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
          detail="Failed to get user's schedule.",
        )

    case "teachers":
      teacher = UserBase.model_validate(user)

      schedule = (
        await schedule_db["lessons"]
          .find({"teacher_edbo": teacher.edbo_id})
          .to_list()
        )

      for lesson in schedule:
        lesson.update({"teacher": UserInitial.model_validate(user).model_dump()})

      return schedule


@router.get("/groups/{group}",
  status_code=status.HTTP_200_OK,
  operation_id="GetGroupSchedule",
  response_model=List[SchedulePrivate],
  response_model_exclude_none=True,
  dependencies=[
    Security(get_current_user, scopes=["teacher", "admin"]),
    Depends(limit_dependency)])
async def get_group_schedule(
  group: Annotated[str, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
):
  """
  Get group schedule.
  """
  schedule_db = mongo.get_database("schedule")
  schedule = await schedule_db["lessons"].find({"group.en": group}).to_list()
  return schedule


@router.get("/lessons/{lesson_id}",
  status_code=status.HTTP_200_OK,
  operation_id="GetLessonById",
  response_model=SchedulePrivate,
  response_model_exclude_none=True,
  dependencies=[
      Security(get_current_user, scopes=["teacher", "admin"]),
      Depends(limit_dependency)])
async def get_lesson_by_id(
  lesson_id: Annotated[str, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
):
  """
  Get lesson by ID.
  """
  schedule_db = mongo.get_database("schedule")

  if not (lesson := await schedule_db["lessons"].find_one({"lesson_id": lesson_id})):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Lesson not found."
    )
  return lesson


@router.patch("/lessons/{lesson_id}",
  status_code=status.HTTP_200_OK,
  operation_id="UpdateLesson",
  dependencies=[
    Depends(limit_dependency)])
async def update_lesson(
  lesson_id: Annotated[str, Path()],
  schedule_update: Annotated[ScheduleUpdate, Body()],
  user: Annotated[dict, Security(get_current_user, scopes=["teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
):
  """
  Update a lesson by ID.
  """
  teacher = TeacherBase.model_validate(user)

  schedule_db = mongo.get_database("schedule")

  if schedule_update.subject and schedule_update.subject not in teacher.disciplines:
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="You don't have access to this discipline.",
    )

  lesson = await schedule_db["lessons"].find_one_and_update(
    filter={"lesson_id": lesson_id},
    update={"$set": schedule_update.model_dump(exclude_unset=True)},
  )

  if not lesson:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Lesson not found."
    )

  return {"message": "The lesson has been successfully updated."}


@router.delete("/lessons/{lesson_id}",
  status_code=status.HTTP_204_NO_CONTENT,
  operation_id="DeleteLesson",
  dependencies=[
      Security(get_current_user, scopes=["teacher", "admin"]),
      Depends(limit_dependency)])
async def delete_lesson(
  lesson_id: Annotated[str, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
):
  """
  Delete a lesson by ID.
  """
  schedule_db = mongo.get_database("schedule")

  if not await schedule_db["lessons"].find_one_and_delete({"lesson_id": lesson_id}):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found."
    )

  return {"message": "The lesson has been deleted."}


@router.post("/lessons/{lesson_id}/attachments",
  status_code=status.HTTP_200_OK,
  operation_id="UploadAttachments",
  response_model=List[MetaFile],
  response_model_exclude_none=True,
  dependencies=[
    Depends(limit_dependency)])
async def upload_attachments(
  lesson_id: Annotated[str, Path()],
  files: Annotated[List[UploadFile], File()],
  user: Annotated[dict, Security(get_current_user, scopes=["teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
):
  """
  Upload attachments.
  """
  teacher = TeacherBase.model_validate(user)

  schedule_db = mongo.get_database("schedule")

  if not (await schedule_db["lessons"].find_one(
    filter={"teacher_edbo": teacher.edbo_id, "lesson_id": lesson_id}
  )):
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
        unique_filename=True,
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
        ).model_dump()
      )
    except cloudinary.exceptions.Error as err:
      logger.error({"msg": "[x] An error occured while attaching files to the lesson.", "erorr": err, })
      raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Error attaching files.",
    )

  if not (await schedule_db["lessons"].update_one(
    filter={"lesson_id": lesson_id},
    update={"$push": {"attachments": {"$each": attachments}}},
  )):
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="Can't attach your files to the lesson.",
    )

  return attachments


@router.delete("/lessons/{lesson_id}/attachments/{file_id}",
  status_code=status.HTTP_200_OK,
  operation_id="DeleteAttachment",
  dependencies=[
    Depends(limit_dependency)])
async def delete_attachment(
  lesson_id: Annotated[str, Path()],
  file_id: Annotated[str, Path()],
  user: Annotated[dict, Security(get_current_user, scopes=["teacher"])],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
):
  """
  Delete an attachment.
  """
  teacher = TeacherBase.model_validate(user)

  schedule_db = mongo.get_database("schedule")

  if not (schedule_lesson := await schedule_db["lessons"].find_one({
    "teacher_edbo": teacher.edbo_id,
    "lesson_id": lesson_id,
    "attachments": {"$elemMatch": {"file_id": file_id}},
  })):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found."
    )

  file_type = None
  for attachment in schedule_lesson.get("attachments", []):
    if file_id == attachment["file_id"]:
      file_type = attachment["file_type"]
      break

  if not file_type:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="File not found in lesson attachments.",
    )

  try:
    detach_result = cloudinary.uploader.destroy(
      public_id=file_id, resource_type=file_type
    )
  except cloudinary.exceptions.Error as err:
    logger.error({"msg": "[x] An error occured while detaching files from the lesson.", "erorr": err})
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="An error occured while detaching the file.",
    )

  if detach_result != "ok":
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND, detail="File not found in the cloud."
    )

  await schedule_db["lessons"].update_one(
    filter={"lesson_id": lesson_id},
    update={"$pull": {"attachments": {"file_id": file_id}}},
  )

  return {"message": "The file has been successfully detached."}
