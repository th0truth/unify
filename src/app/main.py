from starlette.middleware.cors import CORSMiddleware
from fastapi import FastAPI, status, Request
from contextlib import asynccontextmanager

# Rate Limiting Dependencies
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Local Dependencies
from core.logger import logger
from core.config import settings
from core.schemas.etc import HealthCheck
from core.db import (
  MongoClient,
  RedisClient
)
from api.dependencies import limiter
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

# Attach limiter to the App
app.state.limiter = limiter

# Return a 429 status code when limits are exceeded
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