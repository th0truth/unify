# Unified API

Unified API is an asynchronous FastAPI service for education management workflows. It provides versioned REST endpoints for authentication, user profiles, groups, students, teachers, schedules, lesson attachments, and assessment data.

The service is designed around a MongoDB-backed domain model, Redis-backed caching and rate limiting, JWT authentication, Google OAuth, and containerized deployment with Docker Compose and Nginx.

## Features

- **FastAPI application** with automatic OpenAPI, Swagger UI, and ReDoc documentation.
- **Versioned REST API** mounted under `/api/v1`.
- **Authentication and authorization** with OAuth2 password login, Google OAuth, RS256 JWTs, token refresh, logout, and Redis-backed token revocation.
- **Role-aware rate limiting** using SlowAPI and Redis.
- **MongoDB integration** through PyMongo's asynchronous client.
- **Redis integration** for user-profile caching, token blacklist entries, and limiter storage.
- **Education domain endpoints** for users, groups, students, teachers, schedules, grades, assessments, and lesson files.
- **Cloudinary integration** for lesson attachment uploads.
- **Pydantic settings and schemas** for validation, serialization, and environment-based configuration.
- **Docker-first deployment** with an application container and Nginx reverse proxy.
- **Async test setup** using pytest, pytest-asyncio, HTTPX, and ASGITransport.

## Tech Stack

- Python 3.11+
- FastAPI
- Pydantic v2 and pydantic-settings
- Uvicorn
- MongoDB Atlas-compatible connection string
- Redis
- PyJWT with RS256 signing
- Passlib with Argon2 password hashing
- Authlib for Google OAuth
- SlowAPI for rate limiting
- Cloudinary
- Docker and Docker Compose
- uv for dependency management

## API Overview

The application exposes OpenAPI metadata at:

- `GET /api/openapi.json`

Interactive documentation is available when the service is running:

- Swagger UI: `http://localhost:10000/docs`
- ReDoc: `http://localhost:10000/redoc`

Main API groups:

| Area | Base path | Purpose |
| --- | --- | --- |
| Health | `/api/v1/health` | Service health check |
| Authentication | `/api/v1/auth` | Login, token refresh, logout, and Google OAuth |
| Current user | `/api/v1/user` | Current profile, initial data, email/password updates, recovery |
| Users | `/api/v1/users` | User lookup, updates, deletion, and role-based listing |
| Groups | `/api/v1/groups` | Group creation, lookup, listing, and deletion |
| Students | `/api/v1/students` | Student creation, group membership, disciplines, grades, and assessments |
| Teachers | `/api/v1/teachers` | Teacher creation and assigned groups/disciplines |
| Schedule | `/api/v1/schedule` | Lesson scheduling, lesson updates, deletion, and attachments |

## Project Structure

```text
.
├── src/app
│   ├── api                 # FastAPI routers and dependencies
│   ├── core                # Configuration, database clients, middleware, security, schemas
│   ├── crud                # MongoDB data-access helpers
│   └── main.py             # FastAPI application factory and lifespan hooks
├── src/tests               # Async route tests
├── nginx/default.conf      # Nginx reverse proxy configuration
├── scripts                 # Build, run, and clean helper scripts
├── compose.yaml            # Docker Compose services
├── Dockerfile              # Application image
├── pyproject.toml          # Python dependencies and project metadata
├── uv.lock                 # Locked dependency graph
└── pytest.ini              # Test configuration
```

## Requirements

- Python 3.11 or newer
- Docker and Docker Compose
- A MongoDB database
- A Redis instance
- Google OAuth credentials
- Cloudinary credentials
- uv, if running locally outside Docker

## Configuration

Create a local environment file from the example:

```bash
cp .env.example .env
```

Fill in all required values in `.env`.

Important settings:

| Variable group | Description |
| --- | --- |
| `NAME`, `DESCRIPTION`, `SUMMARY`, `VERSION` | FastAPI metadata shown in generated docs |
| `FRONTEND_HOST`, `BACKEND_CORS_ORIGINS` | CORS and session-related origins |
| `MONGO_*` | MongoDB hostname, credentials, database name, and pool settings |
| `REDIS_*` | Redis host, port, credentials, database, cache, and limiter storage |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google OAuth client credentials |
| `SECRET_KEY` | Starlette session middleware secret |
| `RATE_LIMIT_*` | Request limits for admins, students, teachers, and anonymous users |
| `CLOUDINARY_*` | Cloudinary upload credentials |
| `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES` | JWT signing algorithm and token lifetime |

`BACKEND_CORS_ORIGINS` accepts a comma-separated list, for example:

```env
BACKEND_CORS_ORIGINS=http://localhost,http://localhost:10000,https://example.com
```

## Local Development

Install dependencies and create a virtual environment:

```bash
bash scripts/build.sh
```

Activate the environment:

```bash
source .venv/bin/activate
```

Run the API locally:

```bash
PYTHONPATH=src/app uv run uvicorn main:app --host 0.0.0.0 --port 10000 --reload
```

The API will be available at:

```text
http://localhost:10000
```

## Docker Usage

Build and start the application stack:

```bash
bash scripts/run.sh
```

This runs:

- the FastAPI application container
- the Nginx reverse proxy container

Both services use host networking as configured in `compose.yaml`.

To stop the stack:

```bash
docker compose down
```

## Testing

Run the test suite with:

```bash
uv run pytest
```

The pytest configuration sets `src/app` as the Python path and discovers tests under `src/tests`.

## Runtime Behavior

On startup, the FastAPI lifespan handler connects to Redis and MongoDB. On shutdown, both clients are closed cleanly.

Authentication uses bearer tokens issued by `/api/v1/auth/login`. JWT IDs are tracked in Redis when tokens are refreshed or revoked so logged-out tokens cannot be reused. User profile data can also be cached in Redis to reduce MongoDB reads.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.