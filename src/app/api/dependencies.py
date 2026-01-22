from typing import Annotated, Union, AsyncGenerator
from fastapi import Depends, Request, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from redis.asyncio import Redis
from datetime import timedelta
import json

# Rate Limiting Dependencies
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Local Dependencies
from core.logger import logger
from core.config import settings, REDIS_URI, RATE_LIMITS
from core.security.jwt import OAuthJWTBearer
from core.db import MongoClient, RedisClient
from crud import UserCRUD

# OAuth2 scheme for authentication
oauth2_scheme = OAuth2PasswordBearer(
  tokenUrl=f"{settings.API_V1_STR}/auth/login",
)

# Initialize SlowAPI Limiter
limiter = Limiter(
  key_func=get_remote_address,
  storage_uri=REDIS_URI,
  strategy="moving-window",
  headers_enabled=False
)

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


async def get_current_user(
  token: Annotated[str, Depends(oauth2_scheme)],
  redis: Annotated[Redis, Depends(get_redis_client)],
  mongo: Annotated[MongoClient, Depends(get_mongo_client)],
  security_scopes: SecurityScopes
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
  user = None

  # Check if user data exists in Redis cache
  if (user_cache := await redis.get(redis_key)):
    try:
      user = json.loads(user_cache)
    except json.JSONDecodeError as e:
      logger.error({"message": "[x] An error occured while decoding user's data from Redis cache.", "detail": str(e)}, exc_info=True)
      user = None

  # If not in cache or cache failed, check MongoDB    
  if user is None:
    users_db = mongo.get_database("users")
    if not (user := await UserCRUD(users_db).find(username=username, exclude=["_id", "password"])):
      raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Couldn't validate user credentials.",
        headers={"WWW-Authenticate": "Bearer"}
      )
  
    # Store user profile in Redis cache
    await redis.setex(f"cache:user:{username}:profile", timedelta(minutes=settings.CACHE_EXPIRE_MINUTES).seconds, json.dumps(user, default=str))
  
  # Check a user's privileges 
  if security_scopes.scopes:
    user_scopes = user.get("scopes", [])
    if not any(scope in security_scopes.scopes for scope in user_scopes):    
      raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not enough permissions."
      )
    
  return user


def get_user_role(request: Request) -> Union[str, None]:
  """Extract the user's role from the JWT payload."""
  if (auth_token := request.headers.get("Authorization")):
    access_token = auth_token.split()[1]
    if (payload := OAuthJWTBearer.decode(token=access_token)):
      return payload.get("role")
  return


def get_limit_by_role(request: Request) -> Union[str, None]:
  """Declare a Rate Limit dependency."""
  role = get_user_role(request)
  limit = RATE_LIMITS.get(role, "5/minute")

  # Create unique key combining role and IP
  # key = f"{role}:{get_remote_address(request)}"

  # Define a function that slowapi can decorate
  @limiter.limit(limit)
  def _rate_limit_check(request: Request):
    """Dummy function for rate limit check"""
    pass


  # Check rate limit manually
  try:
    _rate_limit_check(request)
  except RateLimitExceeded:
    raise HTTPException(
      status_code=status.HTTP_429_TOO_MANY_REQUESTS,
      detail="Rate limit exceeded."
    )
  return role
