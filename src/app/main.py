from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi import FastAPI, status

# Local Dependencies
from core.logger import logger
from core.config import settings
from core.schemas.etc import HealthCheck
from core.db import (
  MongoClient,
  RedisClient
)
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

@app.get("/health",
  tags=["Health Check"],
  summary="Perform a Health Check",
  response_description="Return HTTP Status Code 200 (OK)",
  status_code=status.HTTP_200_OK,
  response_model=HealthCheck)
async def healt_check():
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