# 🏥 Unified Personal Health Record (PHR) System — Backend

> Production-grade FastAPI backend for aggregating, normalizing, and securely sharing personal health records. Built like a team from Apple, Stripe, and Google Health would.

---

## 🏗️ Architecture Overview

```
phr-backend/
├── app/
│   ├── main.py                  ← FastAPI app, middleware, route registration
│   ├── core/
│   │   ├── config.py            ← Pydantic Settings (env-driven)
│   │   ├── database.py          ← Async SQLAlchemy engine + Base model
│   │   └── security.py          ← JWT creation/validation, bcrypt, RBAC deps
│   ├── models/
│   │   └── models.py            ← Complete DB schema (13 models, 10 enums)
│   ├── schemas/
│   │   └── schemas.py           ← Pydantic v2 request/response models
│   ├── routes/
│   │   ├── auth.py              ← /auth — register, login, refresh, /me
│   │   ├── users.py             ← /users — profile management
│   │   ├── patients.py          ← /patients — profile, vitals, health score
│   │   ├── doctors.py           ← /doctors — doctor profile
│   │   ├── labs.py              ← /labs — lab profile
│   │   ├── reports.py           ← /reports — upload + manage health reports
│   │   ├── prescriptions.py     ← /prescriptions — doctor-written Rx
│   │   ├── appointments.py      ← /appointments — scheduling
│   │   ├── consent.py           ← /consent — ABDM-style consent lifecycle
│   │   ├── notifications.py     ← /notifications — in-app notifications
│   │   ├── ai_insights.py       ← /insights — AI health insights
│   │   └── audit.py             ← /audit — tamper-evident audit logs
│   ├── services/
│   │   ├── auth_service.py      ← Login, register, refresh logic
│   │   ├── ai_service.py        ← AI engine (trend + anomaly detection)
│   │   ├── consent_service.py   ← Consent request lifecycle
│   │   ├── file_service.py      ← File upload/delete
│   │   └── audit_service.py     ← Audit log helper
│   └── middleware/
│       └── logging_middleware.py ← Request/response structured logging
├── alembic/                     ← Database migrations
├── tests/
│   └── test_api.py              ← Async test suite
├── docker-compose.yml           ← Full stack local dev
├── Dockerfile
├── requirements.txt
├── .env.example
└── alembic.ini
```

---

## 🗄️ Database Schema

### Core Tables

| Table | Purpose |
|---|---|
| `users` | Auth + role (patient/doctor/lab/admin) |
| `patients` | Extended patient profile, ABHA ID |
| `doctors` | Registration, specialization, hospital |
| `labs` | Lab name, license, accreditation |
| `vitals` | Time-series vital signs (heart rate, BP, glucose…) |
| `reports` | Uploaded PDF/image health reports |
| `prescriptions` | Doctor-issued prescriptions with medications JSON |
| `appointments` | Scheduled consultations (in-person + telemedicine) |
| `consent_requests` | ABDM-style consent with time-limited access tokens |
| `notifications` | In-app notification inbox |
| `ai_insights` | AI-generated trend/anomaly health insights |
| `audit_logs` | Tamper-evident action log for every sensitive operation |

---

## 🔐 Security Model

- **JWT** (HS256): Access tokens (60 min) + Refresh tokens (7 days)
- **bcrypt** password hashing (cost factor 12)
- **RBAC** via `require_role()` dependency factory — routes enforce roles at the decorator level
- **Consent gating** — doctor data access is checked against active, non-expired consent tokens
- **Audit logging** — every login, data share, consent action, and CRUD write is recorded with user ID, IP, and timestamp

---

## 🧠 AI Engine

The `AIInsightEngine` in `app/services/ai_service.py` runs three algorithms:

| Algorithm | Trigger | Output |
|---|---|---|
| **Range violation** | Latest readings outside normal/critical thresholds | WARNING or CRITICAL insight |
| **Z-score anomaly** | Latest reading > 2σ from 90-day mean | Anomaly insight with % deviation |
| **Linear trend** | Slope > 8% change/week over 90 days | Trend insight (increasing/decreasing) |

Metrics analyzed: heart rate, systolic/diastolic BP, blood glucose, SpO₂, temperature, weight.

Analysis is triggered automatically after every vital signs submission.

---

## 🔗 Consent System (ABDM-Style)

```
Doctor                Patient
  │                      │
  │── POST /consent/request ──▶│
  │                      │  (NotificationType.CONSENT_REQUEST)
  │                      │
  │◀── POST /consent/{id}/respond ─│  (approve / reject)
  │                      │
  │  [Access window opens]│
  │                      │
  │◀── POST /consent/{id}/revoke ──│  (patient can revoke anytime)
```

Each consent has:
- `data_types[]` — which record categories are shared (reports, vitals, prescriptions)
- `expires_at` — hard expiry (max 365 days)
- `access_from` / `access_to` — date range for historical data access
- `token` — cryptographically secure artifact token (32 bytes URL-safe)

---

## 🚀 Quick Start

### Option A — Docker (Recommended)

```bash
# 1. Clone and enter the backend directory
cd phr-backend

# 2. Copy env file
cp .env.example .env
# Edit .env and change SECRET_KEY and JWT_SECRET_KEY

# 3. Start everything
docker compose up --build

# 4. API is live at:
#    http://localhost:8000
#    http://localhost:8000/api/docs  ← Swagger UI
#    http://localhost:8000/api/redoc ← ReDoc
```

### Option B — Local Python

```bash
# Prerequisites: Python 3.12+, PostgreSQL 15+

# 1. Create virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup PostgreSQL
createdb phr_db
createuser phr_user
psql -c "ALTER USER phr_user WITH PASSWORD 'phr_password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE phr_db TO phr_user;"

# 4. Configure environment
cp .env.example .env
# Edit DATABASE_URL if your creds differ

# 5. Run migrations
alembic upgrade head

# 6. Start the server
uvicorn app.main:app --reload --port 8000
```

---

## 📡 API Reference

### Authentication

```
POST /api/v1/auth/register     Register (patient / doctor / lab)
POST /api/v1/auth/login        Login → access + refresh tokens
POST /api/v1/auth/refresh      Refresh access token
GET  /api/v1/auth/me           Current user info
```

### Patients

```
GET  /api/v1/patients/me           My profile
PUT  /api/v1/patients/me           Update profile
POST /api/v1/patients/me/vitals    Log vital signs
GET  /api/v1/patients/me/vitals    Vital history (paginated)
GET  /api/v1/patients/me/health-score  AI health score
GET  /api/v1/patients/             List patients [Doctor/Admin]
GET  /api/v1/patients/{id}         Patient detail [Doctor/Admin]
```

### Reports

```
POST /api/v1/reports/upload    Upload PDF/image report
GET  /api/v1/reports/my        My reports (paginated + filtered)
GET  /api/v1/reports/{id}      Report detail
DELETE /api/v1/reports/{id}    Delete report
```

### Consent

```
POST /api/v1/consent/request           Doctor requests access
POST /api/v1/consent/{id}/respond      Patient approve/reject
POST /api/v1/consent/{id}/revoke       Patient revokes
GET  /api/v1/consent/my                My consent requests
```

### Prescriptions

```
POST /api/v1/prescriptions/    Create [Doctor]
GET  /api/v1/prescriptions/my  My prescriptions
GET  /api/v1/prescriptions/{id}
```

### Appointments

```
POST  /api/v1/appointments/    Schedule
GET   /api/v1/appointments/my  My appointments
PATCH /api/v1/appointments/{id} Update status/notes
DELETE /api/v1/appointments/{id} Cancel
```

### AI Insights

```
GET  /api/v1/insights/my             My AI insights
POST /api/v1/insights/run-analysis   Trigger fresh analysis
POST /api/v1/insights/{id}/acknowledge
GET  /api/v1/insights/health-score
```

### Notifications

```
GET  /api/v1/notifications/             All notifications
GET  /api/v1/notifications/unread-count
POST /api/v1/notifications/{id}/read
POST /api/v1/notifications/mark-all-read
```

---

## 🧪 Running Tests

```bash
# Requires a test database: phr_test
createdb phr_test

# Run all tests with coverage
pytest tests/ -v --cov=app --cov-report=term-missing

# Run specific test file
pytest tests/test_api.py -v -k "test_login"
```

---

## 🌐 Deployment

### Railway / Render

1. Push the `phr-backend/` folder to a GitHub repo
2. Connect to Railway or Render
3. Set environment variables (copy from `.env.example`)
4. Set start command:
   ```
   alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

### Environment Variables (Production Checklist)

```bash
APP_ENV=production
DEBUG=False
SECRET_KEY=<32+ random bytes>      # openssl rand -hex 32
JWT_SECRET_KEY=<64+ random bytes>  # openssl rand -hex 64
DATABASE_URL=postgresql+asyncpg://...
ALLOWED_ORIGINS=["https://your-frontend.vercel.app"]
```

---

## 📋 Next Steps → Frontend

The frontend (Next.js 14 + Tailwind + Framer Motion) connects to these exact API endpoints.

Key integration points:
- All authenticated requests: `Authorization: Bearer <access_token>`
- File uploads: `multipart/form-data` to `POST /api/v1/reports/upload`
- Polling for notifications: `GET /api/v1/notifications/unread-count` every 30s
- AI insights: Auto-generated on vital submission, fetch via `GET /api/v1/insights/my`
