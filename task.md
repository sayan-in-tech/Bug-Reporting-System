# AI4Bharat Backend Hiring Challenge

## Overview

This assignment evaluates your ability to design and implement a **production-ready backend system** with strong foundations in:

- RESTful API design  
- Backend architecture  
- Security best practices  
- DevOps and containerization  
- CI/CD automation  
- Infrastructure readiness  

The goal is to build a **Bug Reporting System API** suitable for real production use.

---

## Tech Stack Requirements

| Category | Requirement |
|--------|-------------|
| Backend | Python (framework of your choice) |
| Containerization | Docker, Docker Compose |
| Orchestration | Kubernetes or Docker Swarm |
| CI/CD | GitHub Actions or GitLab CI |

---

## Objective

Design and implement a production-ready backend API for a bug reporting system with emphasis on:

- Clean, well-structured RESTful API design  
- Containerization with Docker and orchestration readiness  
- Security best practices and vulnerability mitigation  
- CI/CD pipelines with automated testing  
- Production-grade infrastructure configuration  

This assignment evaluates backend architecture, API design, DevOps practices, security implementation, and infrastructure skills.

---

## Context

You are building an **internal bug tracker API** for a team of approximately **50 developers across 10 projects**.

The system must:

- Handle production traffic  
- Be easily deployable across environments  
- Follow strong security best practices  

Document framework choices, architectural decisions, and security considerations in the README.

---

## Part 1: API Design and Implementation

Choose any Python web framework (Django + DRF, FastAPI, Flask, Litestar, etc.).

### 1. User Model

| Field | Type | Constraints |
|-----|------|------------|
| id | UUID / Int | Primary key |
| username | String | Unique, max 50 chars |
| email | String | Unique, valid email |
| password | String | Hashed (bcrypt or argon2), min 8 chars |
| role | Enum | developer, manager, admin |
| is_active | Boolean | Default: true |
| created_at | DateTime | Auto-set |
| last_login | DateTime | Nullable, updated on login |

---

### 2. Project Model

| Field | Type | Constraints |
|-----|------|------------|
| id | UUID / Int | Primary key |
| name | String | Unique, max 100 chars |
| description | Text | Max 1000 chars, optional |
| created_by | FK → User | Required, protect on delete |
| created_at | DateTime | Auto-set |
| updated_at | DateTime | Auto-update |
| is_archived | Boolean | Default: false |

**Business Rules**

- Soft delete via `is_archived`
- Only creator or admin can archive

---

### 3. Issue Model

| Field | Type | Constraints |
|-----|------|------------|
| id | UUID / Int | Primary key |
| title | String | Max 200 chars |
| description | Text | Max 5000 chars, markdown supported |
| status | Enum | open, in_progress, resolved, closed, reopened |
| priority | Enum | low, medium, high, critical |
| project | FK → Project | Required, cascade on delete |
| reporter | FK → User | Required, protect on delete |
| assignee | FK → User | Nullable, set null on delete |
| due_date | Date | Optional |
| created_at | DateTime | Auto-set |
| updated_at | DateTime | Auto-update |

#### Status Transition State Machine

open → in_progress → resolved → closed
↘ reopened ←


**Business Rules**

- Status transitions must follow state machine
- Critical issues cannot be closed without at least one comment

---

### 4. Comment Model

| Field | Type | Constraints |
|-----|------|------------|
| id | UUID / Int | Primary key |
| content | Text | Max 2000 chars, required |
| issue | FK → Issue | Required, cascade on delete |
| author | FK → User | Required, protect on delete |
| created_at | DateTime | Auto-set |
| updated_at | DateTime | Auto-update |

**Business Rules**

- Comments cannot be deleted (audit trail)

---

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|------|----------|-------------|
| POST | /api/auth/register | Register user |
| POST | /api/auth/login | Obtain access + refresh tokens |
| POST | /api/auth/refresh | Refresh access token |
| POST | /api/auth/logout | Invalidate refresh token |
| GET | /api/auth/me | Current user profile |

**Requirements**

- JWT-based auth  
- Access token expiry: 15 minutes  
- Refresh token expiry: 7 days  
- Token blacklisting on logout  

---

### Projects

| Method | Endpoint | Auth |
|------|----------|------|
| GET | /api/projects | Required |
| POST | /api/projects | Required |
| GET | /api/projects/{id} | Required |
| PATCH | /api/projects/{id} | Owner/Admin |
| DELETE | /api/projects/{id} | Owner/Admin |

Query params: `search`, `is_archived`, `page`, `limit`, `sort`

---

### Issues

| Method | Endpoint | Auth |
|------|----------|------|
| GET | /api/projects/{id}/issues | Required |
| POST | /api/projects/{id}/issues | Required |
| GET | /api/issues/{id} | Required |
| PATCH | /api/issues/{id} | Reporter/Assignee/Owner |

Query params: `status`, `priority`, `assignee`, `search`, `sort`, `page`, `limit`

---

### Comments

| Method | Endpoint | Auth |
|------|----------|------|
| GET | /api/issues/{id}/comments | Required |
| POST | /api/issues/{id}/comments | Required |
| PATCH | /api/comments/{id} | Author only |

---

## Permission Matrix

| Action | Anon | Developer | Reporter | Assignee | Manager | Admin |
|------|------|-----------|----------|----------|---------|-------|
| View projects | No | Yes | Yes | Yes | Yes | Yes |
| Create project | No | No | No | No | Yes | Yes |
| Edit project | No | No | No | No | Yes | Yes |
| View issues | No | Yes | Yes | Yes | Yes | Yes |
| Create issue | No | Yes | Yes | Yes | Yes | Yes |
| Edit issue | No | No | Yes | Yes | Yes | Yes |
| Change assignee | No | No | Yes | No | Yes | Yes |
| Add comment | No | Yes | Yes | Yes | Yes | Yes |

Permissions must be implemented using middleware or decorators.

---

## Part 2: Security Requirements

### Authentication and Session Security

- bcrypt or Argon2 hashing  
- Password complexity enforcement  
- JWT with RS256 or ES256  
- Refresh token rotation  
- Rate limiting: 5 login attempts per minute  
- Account lockout after repeated failures  
- Invalidate all sessions on password change  
- Logout all devices support  

---

### Input Validation and Injection Prevention

- Parameterized queries or ORM only  
- No raw SQL string concatenation  
- Sanitize markdown to prevent XSS  
- Content-Security-Policy headers  
- Validate Content-Type  
- Request size limit: 1MB  
- Whitelist query parameters  
- Path traversal protection  

---

### API Security Headers and CORS

- X-Content-Type-Options: nosniff  
- X-Frame-Options: DENY  
- X-XSS-Protection  
- Strict-Transport-Security  
- Strict CORS origin whitelist  
- Rate limiting: 100 requests/min per IP  

---

### Data Protection

- Never log passwords or tokens  
- Mask sensitive fields  
- Field-level encryption if needed  
- Generic client errors  
- Detailed server-side logs  
- Audit logs for auth and permissions  

---

### Dependency Security

- Use safety, pip-audit, or Snyk  
- Pin dependency versions  
- Automated security scans in CI/CD  

---

## Part 3: Containerization and Infrastructure

### Docker

- Multi-stage Dockerfile  
- Non-root user  
- Health checks  
- Layer caching  

### Docker Compose

- API, DB, Redis services  
- Named volumes  
- Env-based config  
- Network isolation  

### Nginx

- Reverse proxy  
- SSL/TLS  
- Load balancing  
- Gzip and caching  

---

### Orchestration (Choose One)

**Option A: Kubernetes**

- Deployment  
- Service  
- ConfigMap and Secrets  
- Ingress  
- HPA  

**Option B: Docker Swarm**

- Stack file  
- Secrets  
- Health checks  
- Rolling updates  

---

## Part 4: CI/CD Pipeline

Pipeline must include:

1. Code quality checks  
2. Testing (≥70% coverage)  
3. Build stage  
4. Deploy stage (bonus)  

Includes:

- Linting  
- Formatting  
- Type checking  
- Security scanning  
- Integration tests  
- Docker image scanning  
- Registry push  

---

## Part 5: Additional Requirements

- Swagger or OpenAPI docs  
- Logging and monitoring  
- Database migrations  
- Load testing (bonus)  
- Consistent error format  
- Seed data scripts  

---

## Submission Guidelines

- Follow repository structure  
- Include README with architecture and security docs  
- CI must pass on main branch  
- Tag final submission version  

---

## Clarifications

- Any Python framework allowed  
- Choose one orchestration platform  
- PostgreSQL recommended  
- Focus on listed security requirements  
- Quality over quantity  

---

**AI4Bharat Confidential**
