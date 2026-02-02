# Bug Reporting System API

A production-ready RESTful API for an internal bug tracking system, built with modern Python technologies and best practices.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Features](#features)
- [Getting Started](#getting-started)
- [API Documentation](#api-documentation)
- [Security](#security)
- [Deployment](#deployment)
- [Testing](#testing)
- [Contributing](#contributing)

## Overview

This Bug Reporting System API is designed to serve approximately 50 developers across 10 projects. It provides a robust platform for tracking software bugs with features including:

- User authentication and authorization
- Project management
- Issue tracking with status workflows
- Comment system for collaboration
- Role-based access control

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          Clients                                 │
│              (Web App, Mobile App, CLI Tools)                   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Nginx Reverse Proxy                          │
│         (SSL/TLS Termination, Load Balancing, Gzip)            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                        │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐ │
│  │ Rate Limiter │ Security     │ Audit Logger │ Request ID   │ │
│  │              │ Headers      │              │              │ │
│  └──────────────┴──────────────┴──────────────┴──────────────┘ │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐ │
│  │ Auth API     │ Projects API │ Issues API   │ Comments API │ │
│  └──────────────┴──────────────┴──────────────┴──────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Service Layer                          │   │
│  │  (Business Logic, State Machine, Permissions)            │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌──────────────────────┐    ┌──────────────────────┐
│    PostgreSQL 16     │    │      Redis 7         │
│   (Primary Storage)  │    │  (Caching, Sessions) │
└──────────────────────┘    └──────────────────────┘
```

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Framework | FastAPI | Async support, built-in OpenAPI, type safety |
| Database | PostgreSQL 16 | Robust, production-ready, excellent ORM support |
| ORM | SQLAlchemy 2.0 | Async support, parameterized queries |
| Migrations | Alembic | Version-controlled schema migrations |
| Cache/Sessions | Redis 7 | Token blacklisting, rate limiting |
| Authentication | JWT (RS256) | Asymmetric signing, refresh token rotation |
| Containerization | Docker | Multi-stage builds, non-root user |
| Orchestration | Kubernetes | HPA, ConfigMaps, Secrets, Ingress |
| CI/CD | GitHub Actions | Automated testing, security scanning |

## Features

### Authentication & Authorization
- JWT-based authentication with RS256 signing
- Access tokens (15-min expiry) and refresh tokens (7-day expiry)
- Refresh token rotation for enhanced security
- Account lockout after failed login attempts
- Session management with logout from all devices

### Role-Based Access Control
| Role | Permissions |
|------|-------------|
| Developer | View projects/issues, create issues, add comments |
| Manager | All developer permissions + create/edit projects, change assignees |
| Admin | Full access to all resources |

### Issue Status Workflow
```
     ┌─────────────────────────────────────────────────────┐
     │                                                     │
     ▼                                                     │
┌─────────┐     ┌─────────────┐     ┌──────────┐     ┌─────────┐
│  OPEN   │────►│ IN_PROGRESS │────►│ RESOLVED │────►│ CLOSED  │
└─────────┘     └─────────────┘     └──────────┘     └─────────┘
     │               │                   │                │
     │               │                   │                │
     │               ▼                   ▼                ▼
     │          ┌─────────┐         ┌──────────┐    ┌──────────┐
     └─────────►│  OPEN   │         │ REOPENED │◄───│ REOPENED │
                └─────────┘         └──────────┘    └──────────┘
```

### Security Features
- Argon2id password hashing
- Rate limiting (100 req/min general, 5 req/min login)
- Security headers (CSP, X-Frame-Options, HSTS, etc.)
- Input sanitization and XSS prevention
- Audit logging for compliance
- Content-Type validation
- Request size limiting (1MB max)

## Getting Started

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- Make (optional)

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/ai4bharat/bug-reporting-system.git
   cd bug-reporting-system
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```

3. **Generate JWT keys**
   ```bash
   python scripts/generate_keys.py
   ```
   Copy the generated keys to your `.env` file.

4. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```

5. **Run database migrations**
   ```bash
   docker-compose exec api alembic upgrade head
   ```

6. **Seed sample data (optional)**
   ```bash
   docker-compose exec api python scripts/seed_data.py
   ```

7. **Access the API**
   - API: http://localhost:8000
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

### Development Without Docker

1. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate     # Windows
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **Start PostgreSQL and Redis** (ensure they're running)

4. **Run migrations**
   ```bash
   alembic upgrade head
   ```

5. **Start the server**
   ```bash
   uvicorn app.main:app --reload
   ```

## API Documentation

### Base URL
```
/api
```

### Authentication Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login and get tokens |
| POST | `/api/auth/refresh` | Refresh access token |
| POST | `/api/auth/logout` | Logout current session |
| GET | `/api/auth/me` | Get current user profile |

### Project Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects` | List all projects |
| POST | `/api/projects` | Create project |
| GET | `/api/projects/{id}` | Get project details |
| PATCH | `/api/projects/{id}` | Update project |
| DELETE | `/api/projects/{id}` | Archive project |

### Issue Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/{id}/issues` | List project issues |
| POST | `/api/projects/{id}/issues` | Create issue |
| GET | `/api/issues/{id}` | Get issue details |
| PATCH | `/api/issues/{id}` | Update issue |

### Comment Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/issues/{id}/comments` | List comments |
| POST | `/api/issues/{id}/comments` | Add comment |
| PATCH | `/api/comments/{id}` | Update comment |

### Query Parameters

**Pagination:**
- `page` - Page number (default: 1)
- `limit` - Items per page (default: 20, max: 100)

**Projects:**
- `search` - Search by name/description
- `is_archived` - Filter by archive status
- `sort` - Sort order (name, -name, created_at, -created_at)

**Issues:**
- `status` - Filter by status
- `priority` - Filter by priority
- `assignee` - Filter by assignee ID
- `search` - Search by title/description
- `sort` - Sort order

### Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format"
      }
    ],
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

## Security

### Authentication Security
- Passwords hashed with Argon2id (memory-hard, GPU-resistant)
- JWT tokens signed with RS256 (asymmetric)
- Access tokens expire in 15 minutes
- Refresh tokens expire in 7 days with rotation
- Token blacklisting on logout
- All sessions invalidated on password change

### Input Validation
- Pydantic models with strict validation
- Markdown content sanitized with Bleach
- Path traversal protection
- Content-Type validation
- Request body size limited to 1MB

### API Security
- CORS with strict origin whitelist
- Security headers on all responses
- Rate limiting per IP address
- Account lockout after 5 failed attempts

### Data Protection
- Passwords and tokens never logged
- Sensitive fields masked in audit logs
- Generic error messages to clients
- Detailed logs server-side only

## Deployment

### Docker Compose (Production)
```bash
# Set environment variables
export DB_USER=postgres
export DB_PASSWORD=secure_password
export DB_NAME=bug_tracker
export REDIS_PASSWORD=secure_password
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Deploy
docker-compose -f docker-compose.prod.yaml up -d
```

### Kubernetes
```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Create secrets (copy and edit secrets.yaml.example)
kubectl apply -f k8s/secrets.yaml

# Deploy all resources
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Environment (development/staging/production) | development |
| `DATABASE_URL` | PostgreSQL connection string | - |
| `REDIS_URL` | Redis connection string | - |
| `SECRET_KEY` | Application secret key | - |
| `JWT_PRIVATE_KEY` | Base64 encoded RSA private key | - |
| `JWT_PUBLIC_KEY` | Base64 encoded RSA public key | - |
| `CORS_ORIGINS` | Comma-separated allowed origins | - |

## Testing

### Run Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_auth.py

# Run with verbose output
pytest -v
```

### Test Coverage
The project maintains a minimum of 70% test coverage. Coverage reports are generated during CI/CD and uploaded to Codecov.

## CI/CD Pipeline

The GitHub Actions pipeline includes:

1. **Lint and Format** - Ruff, Black, isort, mypy
2. **Security Scan** - pip-audit, bandit, safety
3. **Test** - pytest with PostgreSQL and Redis services
4. **Build** - Multi-platform Docker image
5. **Security Scan** - Trivy container scanning
6. **Deploy** - Automated deployment to staging/production

## Project Structure

```
bug-reporting-system/
├── app/
│   ├── api/v1/           # API endpoints
│   ├── core/             # Security, permissions, exceptions
│   ├── middleware/       # Custom middleware
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   ├── utils/            # Utilities
│   ├── config.py         # Settings
│   ├── database.py       # Database setup
│   ├── main.py           # FastAPI app
│   └── redis.py          # Redis setup
├── alembic/              # Database migrations
├── k8s/                  # Kubernetes manifests
├── nginx/                # Nginx configuration
├── scripts/              # Utility scripts
├── tests/                # Test suite
├── docker-compose.yaml   # Development setup
├── docker-compose.prod.yaml  # Production setup
├── Dockerfile            # Container image
└── requirements.txt      # Dependencies
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

---

**AI4Bharat** - Building AI for India
