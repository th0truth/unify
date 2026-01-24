from starlette.middleware.cors import CORSMiddleware
from fastapi import FastAPI, status, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

# Rate Limiting Dependencies
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Local Dependencies
from core.middleware.limiter import RateLimitMiddleware 

from core.logger import logger
from core.config import settings, REDIS_URI
from core.schemas.etc import HealthCheck
from core.db import (
  MongoClient,
  RedisClient
)
from api.dependencies import get_identifier
from api.api import api_main_router

# Initilize lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
  try:
    await RedisClient.connect()
    await MongoClient.connect()
    logger.info("[+] The application has started successfully.")
    yield
  finally:    
    await MongoClient.close()
    await RedisClient.close()


# Initialize an app
app = FastAPI(
  title=settings.NAME,
  description=settings.DESCRIPTION,
  summary=settings.SUMMARY,
  version=settings.VERSION,
  openapi_url="/api/openapi.json",
  lifespan=lifespan
)


# Initialize SlowAPI limiter
limiter = Limiter(
  key_func=get_identifier,
  default_limits=["20/minute"],
  strategy="moving-window",
  storage_uri=REDIS_URI,
  headers_enabled=False,
  swallow_errors=False
)


# Add middleware BEFORE slowapi middleware
app.add_middleware(RateLimitMiddleware)

# Attach limiter to the App
app.state.limiter = limiter

async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
  return JSONResponse(
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    content={"detail": "Rate limit exceeded. Please try again later."}
  )

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/health",
  tags=["Health Check"],
  summary="Perform a Health Check",
  response_description="Return HTTP Status Code 200 (OK)",
  status_code=status.HTTP_200_OK,
  response_model=HealthCheck)
@limiter.exempt
async def healt_check(request: Request):
  return HealthCheck(status="ok")

# Set all CORS enabled origins
if settings.all_cors_origins:
  # Add middlewares
  app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.all_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
  )

# Include main router to the app
app.include_router(api_main_router)