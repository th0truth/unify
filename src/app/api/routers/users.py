from typing import Annotated, Optional, List
from fastapi import (
  APIRouter,
  HTTPException,
  status,
  Security,
  Depends,
  Path,
  Query,
  Body
)
import json
from datetime import timedelta

from core.logger import logger
from core.config import settings
from core.schemas.user import UserBase, UserUpdate
from core.db import MongoClient
from redis.asyncio import Redis
from api.dependencies import (
  get_mongo_client,
  get_redis_client,
  get_current_user
)
from core.crud import UserCRUD
import crud

router = APIRouter(tags=["Users"])
    
@router.get("/{edbo_id}",
  status_code=status.HTTP_200_OK,
  response_model=UserBase,
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def read_user(
  edbo_id: Annotated[int, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  redis: Annotated[Redis, Depends(get_redis_client)]
):
  """
  Returns user data by `edbo_id`.
  """
  redis_key = f"cache:user:{edbo_id}:profile"
  try:
    # Check if user data exists in Redis cache
    if (user_cache := await redis.get(redis_key)):
      try:
        # Parse user data to the JSON format
        user = json.loads(user_cache)
        return user
      except json.JSONDecodeError:
        pass

    
    # Check if user exists in MongoDB
    users_db = mongo.get_database("users")
    if not (user := await UserCRUD(users_db).find(username=edbo_id)):
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="User not found."
      )
    
    # Store user data in Redis cache 
    await redis.setex(redis_key, timedelta(minutes=settings.CACHE_EXPIRE_MINUTES).seconds, json.dumps(user, default=str))
    return user
  except Exception as err:
    logger.error(err)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="Internal server error."
    )

@router.get("/{role}/all",
  status_code=status.HTTP_200_OK,
  response_model=List[UserBase],
  dependencies=[Security(get_current_user, scopes=["admin"])])
async def read_users(
  role: Annotated[str, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],   
):
  """
  Returns all users.
  """
  users_db = mongo.get_database("users")
  return await UserCRUD(users_db).read_all(role)

@router.patch("/{role}/update",
  status_code=status.HTTP_200_OK,
  dependencies=[Security(get_current_user, scopes=["admin"])])
async def update_all_users(
  role: Annotated[str, Path()],
  update_user: Annotated[UserUpdate, Body()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Updates users data.
  """
  users_db = mongo.get_database("users")
  await crud.update_all_users(users_db, role=role, update_doc=update_user)
  
  return {"message": "User accounts has been updated."}

@router.patch("/{edbo_id}/update",
  status_code=status.HTTP_200_OK,
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def update_user(
  edbo_id: Annotated[int, Path()],
  update_user: Annotated[UserUpdate, Body()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  redis: Annotated[Redis, Depends(get_redis_client)]
):
  """
  Updates user data by `edbo_id`.
  """
  users_db = mongo.get_database("users")
  
  # Update the user data
  await crud.update_user(users_db, edbo_id=edbo_id, update_doc=update_user)
  
  # Delete user profile from Redis cache
  await redis.delete(f"cache:user:{edbo_id}:profile")

  return {"message": "The user account has been updated."}

@router.delete("/{edbo_id}/delete",
  status_code=status.HTTP_200_OK,
  dependencies=[Security(get_current_user, scopes=["admin"])])
async def delete_user(
  edbo_id: Annotated[int, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  redis: Annotated[Redis, Depends(get_redis_client)]
):
  """
  Deletes an exiting user account.
  """
  users_db = mongo.get_database("users")

  # Delete the user account
  await crud.delete_user(users_db, edbo_id=edbo_id)

  # Delete user profile from Redis cache
  await redis.delete(f"cache:user:{edbo_id}:profile")

  return {"message": "The user account has been deleted."}