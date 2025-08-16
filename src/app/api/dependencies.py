from typing import Annotated, AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from datetime import timedelta
import json

from core.config import settings
from core.logger import logger

from core.security.jwt import OAuthJWTBearer
from core.db import MongoClient, RedisClient
from core.schemas.token import TokenData
from core.crud import UserCRUD

async def get_mongo_client() -> AsyncGenerator[MongoClient, None]:
  """Dependency to get MongoDB client."""
  if not MongoClient._client:
    await MongoClient.connect()
  yield MongoClient._client

async def get_redis_client() -> AsyncGenerator[RedisClient, None]:
  """Dependency to get Redis client."""
  if not RedisClient._client:
    await RedisClient.connect()
  yield RedisClient._client

# OAuth2 scheme for authentication
oauth2_scheme = OAuth2PasswordBearer(
  tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

async def get_current_user(
  token: Annotated[str, Depends(oauth2_scheme)],
  redis: Annotated[Redis, Depends(get_redis_client)],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
) -> dict:
  # Decode the user's JWT
  if not (payload := OAuthJWTBearer.decode(token=token)):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Invalid token.",
    )
  
  # Get data from the payload   
  username, jti = payload.get("sub"), payload.get("jti")
  
  # Check if jti is revoked
  if await OAuthJWTBearer.is_jti_in_blacklist(redis, jti=jti):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Token has been revoked."
    )

  redis_key = f"cache:user:{username}:profile"

  try:
    # Check if user data exists in Redis cache
    if (user_cache := await redis.get(redis_key)):
      try:
        user = json.loads(user_cache)
        return user
      except json.JSONDecodeError:
        pass
    
    # Check if user exists in MongoDB
    users_db = mongo.get_database("users")
    if not (user := await UserCRUD(users_db).get_by_username(username=username, exclude=["_id", "password"])):
      raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Couldn't validate user credentials.",
        headers={"WWW-Authenticate": "Bearer"}
      )

    # Store user profile in Redis cache
    await redis.setex(f"cache:user:{username}:profile", timedelta(minutes=settings.CACHE_EXPIRE_MINUTES).seconds, json.dumps(user, default=str))

    return user
  except Exception as err:
    logger.error(err)
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="Internal server error."
    ) 