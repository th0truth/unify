from typing import Annotated
from datetime import timedelta
from fastapi import (
  BackgroundTasks,
  HTTPException,
  APIRouter,
  status,
  Depends,
  Body
)
from core.config import settings
from core.schemas.user import UserInitial
from core.schemas.etc import UpdateEmail, UpdatePassword, PasswordRecovery
from core.security.utils import Hash, send_email, render_template, generate_verification_code
from core.db import MongoClient
from redis.asyncio import Redis
from api.dependencies import (
  get_mongo_client,
  get_redis_client,
  get_current_user
)
from crud import UserCRUD

router = APIRouter(tags=["User"])

@router.get("/me",
  status_code=status.HTTP_200_OK,
  operation_id="GetCurrentUser",
  response_model_exclude={"password"},
  response_model_exclude_none=True)
async def get_active_user(
  user: Annotated[dict, Depends(get_current_user)]
):
  """
  Returns user data.
  """
  return user


@router.get("/initial", 
  status_code=status.HTTP_200_OK,
  operation_id="GetCurrentUserInitial",
  response_model=UserInitial)
async def get_user_initial(
  user: Annotated[dict, Depends(get_current_user)]
):
  """
  Returns user initial.
  """
  return user


@router.patch("/email",
  status_code=status.HTTP_200_OK,
  operation_id="AddEmailToCurrentUser")
async def add_user_email(
  user_update: Annotated[UpdateEmail, Body()],
  user: Annotated[dict, Depends(get_current_user)],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  redis: Annotated[Redis, Depends(get_redis_client)],
  background_tasks: BackgroundTasks
):
  """
  Adds an email to the user account.
  """
  # Get user's email from the MongoDB database
  users_db = mongo.get_database("users")
  if await UserCRUD(users_db).find(username=user_update.email):
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail="That email is already associated with another account."
    )
  
  # Verify the user's credentials
  if not (user := await UserCRUD(users_db).authenticate(username=user.get("edbo_id"), plain_pwd=user_update.password)):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Couldn't validate credentials",
      headers={"WWW-Authenticate": "Bearer"}
    )
  edbo_id = user.get("edbo_id")

  # Update the user data
  await UserCRUD(users_db).update(username=edbo_id, update_doc={"email": {"address": user_update.email, "is_verified": False}})

  # Generate verification code
  verification_code = generate_verification_code()

  hash_key = f"session:code:{verification_code}"
  await redis.hset(hash_key, key=edbo_id, value=verification_code)
  await redis.expire(hash_key, timedelta(minutes=settings.VERIFICATION_CODE_EXPIRE).seconds)

  # Render HTML template
  html_code = render_template(
    template_name="email/verification_code.html",
    context={
      "company": settings.COMPANY_NAME,
      "name": user.get("first_name"),
      "account_name": user_update.email,
      "verification_code": verification_code
    })

  # Send the email
  background_tasks.add_task(
    send_email,
    to=user_update.email,
    subject=f"Hello.",
    html_content=html_code,
    reply_to_name="Support",
  )

  # Delete user profile from Redis cache 
  await redis.delete(f"cache:user:{edbo_id}:profile")

  return {"message": "Email added to the user account."}



@router.patch("/password",
  status_code=status.HTTP_200_OK,
  operation_id="UpdateCurrentUserPassword")
async def update_password_me(
  update_body: Annotated[UpdatePassword, Body()],
  user: Annotated[dict, Depends(get_current_user)],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
):
  """
  Updates the current user's password.
  """
  # Get the user email's from the MongoDB database
  users_db = mongo.get_database("users")

  # Verify the user's credentials
  if not (user := await UserCRUD(users_db).authenticate(username=user.get("edbo_id"), plain_pwd=update_body.current_password)):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Couldn't validate credentials",
      headers={"WWW-Authenticate": "Bearer"}
    )

  # Update the user data
  await UserCRUD(users_db).update(username=user.get("edbo_id"), update={"password": Hash.hash(plain=update_body.new_password)})

  return {"message": "The password was updated."}


@router.patch("/recovery",
  operation_id="RecoverUserPassword",
  status_code=status.HTTP_200_OK)
async def password_recovery(
  update_body: Annotated[PasswordRecovery, Body()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  background_tasks: BackgroundTasks
):
  """
  Password recovery for the current user.
  """
  # Update the user data
  users_db = mongo.get_database("users")
  if not (user := await UserCRUD(users_db).update(username=update_body.email, update={"password": Hash.hash(plain=update_body.new_password)})):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="User not found."
    )

  # Generate verification code
  verification_code = generate_verification_code()

  # Render HTML template
  html_code = render_template(
    template_name="email/reset_password.html",
    context={
      "company": settings.COMPANY_NAME,
      "name": user.get("first_name"),
      "account_name": update_body.email,
      "verification_code": verification_code
    })

  # Send the email
  background_tasks.add_task(
    send_email,
    to=update_body.email,
    subject=f"Hi.",
    html_content=html_code,
    text_content="Description.",
    reply_to_name="Support",
  )

  return {"message": "The user's password has been recovered."}