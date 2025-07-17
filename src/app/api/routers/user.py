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
from core.schemas.etc import UpdateEmail, UpdatePassword, PasswordRecovery
from core.security.utils import Hash, send_email, render_template, generate_verification_code
from core.db import MongoClient
from redis.asyncio import Redis
from api.dependencies import (
  get_mongo_client,
  get_redis_client,
  get_current_user
)
import crud

router = APIRouter(tags=["User"])

@router.get("/me",
  status_code=status.HTTP_200_OK,
  response_model_exclude={"password"},
  response_model_exclude_none=True)
async def get_active_user(
  user: Annotated[dict, Depends(get_current_user)]
):
  """
  Returns user's data.
  """

  return user

@router.patch("/email/update",
  status_code=status.HTTP_200_OK)
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
  if await crud.get_user_by_username(users_db, username=user_update.email):
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail="That email is already associated with another account."
    )
  
  # Verify the user's credentials
  user = await crud.authenticate_user(users_db, username=user.get("edbo_id"), plain_pwd=user_update.password)
  edbo_id = user.get("edbo_id")

  # Update the user data
  await crud.update_user(users_db, edbo_id=edbo_id, update_doc={"email": {"address": user_update.email, "is_verified": False}})

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


@router.patch("/password/update",
  status_code=status.HTTP_200_OK)
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
  user = await crud.authenticate_user(users_db, username=user.get("edbo_id"), plain_pwd=update_body.current_password)

  # Update the user data
  await crud.update_user(users_db, edbo_id=user.get("edbo_id"), update_doc={"password": Hash.hash(plain=update_body.new_password)})

  return {"message": "The password has been updated."}

@router.patch("/password/recovery",
  status_code=status.HTTP_200_OK)
async def password_recovery(
  update_body: Annotated[PasswordRecovery, Body()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  background_tasks: BackgroundTasks
):
  """
  Password recovery for the current user.
  """

  # Get the user's email from the MongoDB database.
  users_db = mongo.get_database("users")
  user = await crud.get_user_by_username(users_db, username=update_body.email)
  if not user:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Can't find your account."
    )
  
  # Generate verification code
  verification_code = generate_verification_code()

  # Update the user data
  await crud.update_user(users_db, edbo_id=user.get("edbo_id"), update_doc={"password": Hash.hash(plain=update_body.new_password)})

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