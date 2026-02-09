from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi import FastAPI
import itsdangerous

# Rate Limiting Dependencies
from slowapi.errors import RateLimitExceeded

# Local Dependencies
from core.middleware.limiter import RateLimitMiddleware 
from core.errors import rate_limit_exceeded_handler

from core.logger import logger
from core.config import settings
from core.database import (
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


def create_app() -> FastAPI:
  # Initialize an app
  app = FastAPI(
    title=settings.NAME,
    description=settings.DESCRIPTION,
    summary=settings.SUMMARY,
    version=settings.VERSION,
    openapi_url="/api/openapi.json",
    lifespan=lifespan
  )


  # Add middleware RateLimitMiddleware
  app.add_middleware(RateLimitMiddleware)
  app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="session",
    max_age=3600,
    same_site="lax",
    https_only=False
  )

  # Attach limiter to the app
  app.state.limiter = limiter
  app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

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
  return app


# Create the app instance at module level
app = create_app()


if __name__ == "__main__":
  import uvicorn
  uvicorn.run(
    app="main:app",
    host="0.0.0.0",
    port=10000,
    reload=True,
    log_level="info"
  )
