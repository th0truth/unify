from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from pydantic import BaseModel, AnyUrl, BeforeValidator, computed_field
from typing import Any, TypeVar, Annotated, List

# Define a generic type variable
ModelType = TypeVar("TypeModel", bound=BaseModel)


# Parse middleware cors
def parse_cors(v: Any) -> List[str] | str:
  if isinstance(v, str) and not v.startswith("["):
    return [i.strip() for i in v.split(",")]
  elif isinstance(v, list | str):
    return v
  raise ValueError(v)

# Generate private key for JWT
private_key = rsa.generate_private_key(
  public_exponent=65537,
  key_size=2048,
  backend=default_backend()
)

class Settings(BaseSettings): 
  model_config = SettingsConfigDict(
    env_file=".env",
    	env_ignore_empty=True,
      extra="ignore",
  	)
    
  # App settings
  NAME: str
  DESCRIPTION: str = ""
  SUMMARY: str = ""
  VERSION: str = "0.0.1"

  FRONTEND_HOST: str = "http://localhost:10000"

  BACKEND_CORS_ORIGINS: Annotated[
    List[AnyUrl] | str, BeforeValidator(parse_cors)
  ] = []
  
  @computed_field  # type: ignore[prop-decorator]
  @property
  def all_cors_origins(self) -> list[str]:
    return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
      self.FRONTEND_HOST
    ]

  # API versions
  API_V1_STR: str = "/api/v1"
  
  # MongoDB settings    
  MONGO_HOSTNAME: str
  MONGO_USERNAME: str
  MONGO_PASSWORD: str
  MONGO_DATABASE: str
  MONGO_MAX_POOL_SIZE: int = 100
  MONGO_MIN_POOL_SIZE: int = 10
  MONGO_CONNECT_TIMEOUT_MS: int = 10000
  MONGO_SERVER_SELECTION_TIMEOUT_MS: int = 10000
  MONGO_RETRY_WRITES: bool = True
    
  # Redis settings
  REDIS_HOST: str
  REDIS_PORT: int
  REDIS_USERNAME: str
  REDIS_PASSWORD: str
  REDIS_DB: int = 0  
  
  CACHE_EXPIRE_MINUTES: int
  VERIFICATION_CODE_EXPIRE: int

  # Google settings (OAuth)
  GOOGLE_CLIENT_ID: str
  GOOGLE_CLIENT_SECRET: str

  SECRET_KEY: str

  # Rate limits
  RATE_LIMIT_ADMIN: str
  RATE_LIMIT_STUDENT: str
  RATE_LIMIT_TEACHER: str
  RATE_LIMIT_ANONYMOUS: str

  # Cloudinary secrets
  CLOUDINARY_CLOUD_NAME: str
  CLOUDINARY_API_KEY: int
  CLOUDINARY_API_SECRET: str
  
  # JWT settings
  JWT_ALGORITHM: str = "RS256"
  JWT_EXPIRE_MINUTES: int

  # Generate private key in PEM format
  PRIVATE_KEY_PEM: bytes = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
  )

  # Generate public key in PEM format   
  PUBLIC_KEY_PEM: bytes = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
  )

settings = Settings()
  
REDIS_URI = f"redis://{settings.REDIS_USERNAME}:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
RATE_LIMITS = {
  "admins": settings.RATE_LIMIT_ADMIN,
  "students": settings.RATE_LIMIT_STUDENT,
  "teachers": settings.RATE_LIMIT_TEACHER,
  "anonymous": settings.RATE_LIMIT_ANONYMOUS
}