from typing import Annotated
from fastapi import (
  HTTPException,
  APIRouter,
  status,
  Request,
  Depends,
  Body
)

from core.schemas.user import UserInitial
from core.schemas.etc import UpdateEmail, UpdatePassword, PasswordRecovery
from core.security.utils import Hash
from core.db import MongoClient
from redis.asyncio import Redis
from api.dependencies import (
  get_mongo_client,
  get_redis_client,
  get_current_user
)
from api.dependencies import limit_dependency
from crud import UserCRUD

router = APIRouter(tags=["User"])

@router.get("/me",
  status_code=status.HTTP_200_OK,
  operation_id="GetCurrentUser",
  response_model_exclude={"password"},
  response_model_exclude_none=True,
  dependencies=[Depends(limit_dependency)])
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
  response_model=UserInitial,
  dependencies=[Depends(limit_dependency)])
async def get_user_initial(
  user: Annotated[dict, Depends(get_current_user)]
):
  """
  Returns user initial.
  """
  return user


@router.patch("/email",
  status_code=status.HTTP_200_OK,
  operation_id="AddEmailToCurrentUser",
  dependencies=[Depends(limit_dependency)])
async def add_user_email(
  user_update: Annotated[UpdateEmail, Body()],
  user: Annotated[dict, Depends(get_current_user)],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  redis: Annotated[Redis, Depends(get_redis_client)],
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
  
  edbo_id = user.get("edbo_id")

  # Verify the user's credentials
  if not await UserCRUD(users_db).authenticate(username=edbo_id, plain_pwd=user_update.password):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Couldn't validate credentials",
      headers={"WWW-Authenticate": "Bearer"}
    )

  # Update the user data
  await UserCRUD(users_db).update(username=edbo_id, update={"email": {"address": user_update.email, "is_verified": False}})

  # Delete user profile from Redis cache 
  await redis.delete(f"cache:user:{edbo_id}:profile")

  return {"message": "Email added to the user account."}



@router.patch("/password",
  status_code=status.HTTP_200_OK,
  operation_id="UpdateCurrentUserPassword",
  dependencies=[Depends(limit_dependency)])
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

  # Update the user password
  await UserCRUD(users_db).update(username=user.get("edbo_id"), update={"password": Hash.hash(plain=update_body.new_password)})

  return {"message": "The password has been updated."}


@router.patch("/recovery",
  operation_id="RecoverUserPassword",
  status_code=status.HTTP_200_OK,
  dependencies=[Depends(limit_dependency)])
async def password_recovery(
  update_body: Annotated[PasswordRecovery, Body()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
):
  """
  Password recovery for the current user.
  """
  # Update the user password
  users_db = mongo.get_database("users")
  if not await UserCRUD(users_db).update(username=update_body.email, update={"password": Hash.hash(plain=update_body.new_password)}):
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="User not found."
    )

  return {"message": "The user's password has been recovered."}