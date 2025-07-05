from typing import Annotated
from fastapi import (
  HTTPException,
  APIRouter,
  status,
  Depends,
  Body
)
from core.schemas.etc import (
  UpdateEmail,
  UpdatePassword,
  PasswordRecovery
)
from core.security.utils import Hash
from core.db import MongoClient
from api.dependencies import (
  get_mongo_client,
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
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
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

  # Update the user data
  await crud.update_user(users_db, edbo_id=user.get("edbo_id"), update_doc={"email": user_update.email})
  raise HTTPException(
    status_code=status.HTTP_200_OK,
    detail="Email added to the user account."
  )


@router.patch("/password/update",
  status_code=status.HTTP_200_OK)
async def update_password_me(
  update_body: Annotated[UpdatePassword, Body()],
  user: Annotated[dict, Depends(get_current_user)],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
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
  raise HTTPException(
    status_code=status.HTTP_200_OK,
    detail="The password has been updated."
  )

@router.patch("/password/recovery",
  status_code=status.HTTP_200_OK)
async def password_recovery(
  update_body: Annotated[PasswordRecovery, Body()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
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
  
  # Update the user data
  await crud.update_user(users_db, edbo_id=user.get("edbo_id"), update_doc={"password": Hash.hash(plain=update_body.new_password)})
  raise HTTPException(
    status_code=status.HTTP_200_OK,
    detail="The user's password has been recovered."
  )