from typing import Annotated, Optional, List
from fastapi import (
  APIRouter,
  HTTPException,
  status,
  Security,
  Depends,
  Path,
  Query,
  Body,
)
from core.schemas.user import UserBase, UserUpdate
from core.db import MongoClient
from api.dependencies import (
  get_mongo_client,
  get_current_user
)
import crud

router = APIRouter(tags=["Users"])
    
@router.get("/{edbo_id}",
  status_code=status.HTTP_200_OK,
  response_model=UserBase,
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def read_user(
  edbo_id: Annotated[int, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Returns user data by `edbo_id`.
  """
  users_db = mongo.get_database("users")
  user = await crud.read_user(users_db, edbo_id=edbo_id)
  if not user:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="User not found."
    )
  return user

@router.get("/{role}/all",
  status_code=status.HTTP_200_OK,
  response_model=List[UserBase],
  dependencies=[Security(get_current_user, scopes=["admin"])])
async def read_users(
  role: Annotated[str, Path()],
  filter: Annotated[str, Query()],
  value: Annotated[str, Query()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]   
):
  """
  Returns all users.
  """
  users_db = mongo.get_database("users")
  return await crud.read_users(users_db, role=role, filter=filter, value=value)

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
  raise HTTPException(
    status_code=status.HTTP_200_OK,
    detail="User accounts has been updated."
  )

@router.patch("/{edbo_id}/update",
  status_code=status.HTTP_200_OK,
  dependencies=[Security(get_current_user, scopes=["teacher", "admin"])])
async def update_user(
  edbo_id: Annotated[int, Path()],
  update_user: Annotated[UserUpdate, Body()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
):
  """
  Updates user data by `edbo_id`.
  """
  users_db = mongo.get_database("users")
  await crud.update_user(users_db, edbo_id=edbo_id, update_doc=update_user)
  raise HTTPException(
    status_code=status.HTTP_200_OK,
    detail="The user account has been updated."
  )

@router.delete("/{edbo_id}/delete",
  status_code=status.HTTP_200_OK,
  dependencies=[Security(get_current_user, scopes=["admin"])])
async def delete_user(
  edbo_id: Annotated[int, Path()],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)] 
):
  """
  Deletes an exiting user account.
  """
  users_db = mongo.get_database("users")
  await crud.delete_user(users_db, edbo_id=edbo_id)
  raise HTTPException(
      status_code=status.HTTP_200_OK,
      detail="The user account has been deleted"
  )