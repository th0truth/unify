from typing import Annotated, AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import (
  OAuth2PasswordBearer,
  SecurityScopes
)
from redis.asyncio import Redis
from datetime import timedelta
import json

from core.config import settings

from core.security.jwt import OAuthJWTBearer
from core.db import MongoClient, RedisClient
from core.schemas.token import TokenData
import crud

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

oauth2_scheme = OAuth2PasswordBearer(
  tokenUrl=f"{settings.API_V1_STR}/auth/login",
  scopes=settings.scopes
)

async def get_current_user(
  security_scopes: SecurityScopes,
  token: Annotated[str, Depends(oauth2_scheme)],
  redis: Annotated[Redis, Depends(get_redis_client)],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)]
) -> dict:
  # Decode a user's JWT
  payload = OAuthJWTBearer.decode(token=token)
  if not payload:
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
  
  if not (user_cache := await redis.get(f"auth:user:{username}")):
    # Authenticate user data from the MongoDB database
    users_db = mongo.get_database("users")
    # Validate user credentials
    if not (user := await crud.get_user_by_username(users_db, username=username, exclude=["_id", "password"])):
      raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Couldn't validate user credentials.",
        headers={"WWW-Authenticate": "Bearer"}
      )
    # Add user data to the Redis database
    await redis.setex(f"auth:user:{username}", timedelta(minutes=settings.CACHE_EXPIRE_MINUTES).seconds, json.dumps(user, default=str))
  else:
    user = json.loads(user_cache)

  token_data = TokenData(edbo_id=user.get("edbo_id"), scopes=user.get("scopes"))
  
  # Check a user's privileges 
  if security_scopes.scopes:
    for scope in token_data.scopes:
      if scope not in security_scopes.scopes:
        raise HTTPException(
          status_code=status.HTTP_404_NOT_FOUND,
          detail="Not enough permissions."
        )
  return user