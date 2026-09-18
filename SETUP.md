# Development Setup

Run the React frontend and FastAPI backend either with Docker or directly on your computer. Both options use your hosted Neon PostgreSQL database.

All terminal examples use Windows PowerShell. Start in the repository root (`Nebula-X-Hackaton`) unless a section says otherwise.

## 1. Configure environment files

Keep backend and frontend configuration separate. Create the following files if they do not exist. If they already exist, update the relevant settings without replacing your existing credentials.

### Backend: `backend/.env`

```env
APP_ENV=development
DATABASE_URL=postgresql+psycopg://neondb_owner:YOUR_NEON_PASSWORD@ep-fragrant-surf-b3dlf20p-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
JWT_SECRET=REPLACE_WITH_A_RANDOM_SECRET_OF_AT_LEAST_32_CHARACTERS
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
SIGNUP_CODE=defaultcode
FRONTEND_ORIGIN=http://localhost:5173
REDIS_URL=redis://localhost:6379/0
```

- Replace `YOUR_NEON_PASSWORD` with the password from your Neon connection details. URL-encode special characters in the password, such as `@` (`%40`), `#` (`%23`), or `%` (`%25`).
- Use plain underscores and `@` characters in the URL; do not add backslashes or braces.
- Generate a random JWT secret rather than using the example value. With Python installed, run `python -c "import secrets; print(secrets.token_urlsafe(48))"` and paste the result into `JWT_SECRET`.
- Signup requires the value of `SIGNUP_CODE`, initially `defaultcode`. Keep this setting in the backend only.
- Redis integration is still a placeholder; a running Redis server is not required for the current authentication flow.

### Frontend: `frontend/.env`

```env
VITE_API_BASE_URL=http://localhost:8000
```

Frontend variables prefixed with `VITE_` are public. Do not put database credentials, the JWT secret, or the signup code here. Actual `.env` files are Git-ignored; example files must contain placeholders only.

## 2. Run with Docker and auto reload

### Requirements

- Docker Desktop installed and running, with Linux containers enabled.
- A reachable Neon database and both `.env` files configured.
- Ports `5173` and `8000` available. Stop any locally running frontend/backend servers first.

Docker supplies Python and Node.js, so host installations are not required for this option.

### Build and initialize the database

From the repository root:

```powershell
docker compose build
docker compose run --rm backend python -m app.db.init_db
```

The database command creates missing tables, including `users`, in the database named by `DATABASE_URL`. It does not recreate existing tables or apply future schema changes.

Expected output:

```text
Database tables initialized.
```

### Start the application

```powershell
docker compose up
```

Leave this terminal running, or use `docker compose up -d` to run in the background.

| Service | URL |
| --- | --- |
| Frontend | http://localhost:5173 |
| Backend API documentation | http://localhost:8000/docs |
| Backend health check | http://localhost:8000/api/health |

The backend root URL (`http://localhost:8000/`) currently returns `Not Found`; use `/docs` or `/api/health` instead.

### How auto reload works

- React source changes update the browser through Vite.
- Python changes inside `backend/app/` or `backend/scheduler/` restart Uvicorn.
- Code is mounted from your computer into the containers, so ordinary source edits do not require an image rebuild.
- Polling is enabled to detect file changes through Windows/Docker Desktop mounts.

After changing environment files, recreate the services so they load the new values:

```powershell
docker compose up -d --force-recreate
```

Compose explicitly sets `FRONTEND_ORIGIN` to `http://localhost:5173` and `VITE_API_BASE_URL` to `http://localhost:8000`. To change those values for Docker, also update `compose.yaml`.

After changing dependencies, rebuild. Renew the frontend's anonymous dependency volume so it receives the rebuilt `node_modules`:

```powershell
docker compose up -d --build --renew-anon-volumes
```

When changing frontend dependencies, update both `package.json` and `package-lock.json`; the Docker build uses `npm ci`.

### Logs and shutdown

```powershell
docker compose logs -f backend frontend worker
docker compose down
```

Stopping the containers does not remove data from Neon. This Docker configuration is for development, not production deployment.

## 3. Run locally without Docker

### Requirements

- Python 3.11 or newer (3.12 recommended).
- Node.js 22 and npm.
- A reachable Neon database and the environment files from step 1.

### Backend

In a terminal at the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m app.db.init_db
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Skip virtual environment creation if `.venv` already exists. Using its Python executable directly avoids needing to activate it in PowerShell.

### Frontend

Open a second terminal at the repository root:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Use `npm.cmd` on Windows to avoid PowerShell execution-policy errors from `npm.ps1`. Open http://localhost:5173. Leave both terminals running; stop each server with `Ctrl+C`.

Restart the backend after changing `backend/.env`, and restart Vite after changing `frontend/.env`.

### Scheduling worker

For local development, open a third terminal from the repository root:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.workers.dev
```

This worker reloads when backend Python source changes. For a worker without auto reload, use `python -m app.workers.scheduling` instead (with the virtual environment's Python).

Docker Compose starts a worker automatically. Each worker processes one job at a time. PostgreSQL row locking with `SKIP LOCKED` lets multiple workers claim different queued jobs. A user may have at most three queued/running jobs. Interrupted jobs are marked failed after their execution allowance; create a new run to retry them.

After pulling these scheduling changes, rerun `python -m app.db.init_db` using the local virtual environment or the Docker command above. It creates the new `datasets` and `scheduling_runs` tables as well as `users`.

## Scheduling preparation and constraint extension points

1. Sign in and select the eight CSV files from `01_data/` (or a new instance using the same schema).
2. Choose scenario A, B, or C and click **Prepare scenario**.
3. The worker loads the instance, calculates spatial footprints, builds decision variables/objective, and saves a preparation report.
4. The run ends with status `blocked` while railway constraints are missing. This is expected, not a valid possession schedule.

Inputs, run metadata, and reports are stored in PostgreSQL and belong to the signed-in user. Current upload limits are 2 MB per CSV, 1,000 activities/locations, 260 weeks, and a bounded model size; oversized instances are rejected explicitly.

You can prepare the public dataset without the web application or database. From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m scheduler ..\01_data --scenario A --output ..\runtime\preparation-A.json
```

The following modules intentionally contain no railway constraint implementations:

```text
backend/scheduler/constraints/workload.py
backend/scheduler/constraints/safety.py
backend/scheduler/constraints/possessions.py
backend/scheduler/constraints/contracts.py
backend/scheduler/constraints/eclo.py
```

Each provides `add_constraints(model, variables, instance, footprints, policy)`. Implement its rules and accounting relationships before setting its `IMPLEMENTED` flag to `True`. In particular, link the ECLO flags, possession labels, activity lateness, and location excess variables to actual accesses; the objective does not enforce those relationships.

The reference validator is not included in the supplied files. When available, configure `VALIDATOR_COMMAND` in `backend/.env` as a JSON array of executable/arguments using its documented CLI syntax. The adapter replaces `{instance_dir}` and `{submission_dir}` placeholders with temporary input/output directories, executes without a shell, and expects a JSON report on stdout with a boolean `feasible` field. Recreate/restart services after changing this setting.

CSV exports and ZIP packaging are implemented for future solver output. A submission download is enabled only after the configured reference validator confirms feasibility. Otherwise the run is `needs_validation`, with no downloadable submission ZIP. No search or submission export occurs while constraints remain missing.

Spatial footprints currently assume a live closure reaching either interchange hub or its connecting sector triggers the cross-line closure. This interpretation and completion-date conventions still need checking against the reference validator when it becomes available.

## 4. Verify the setup

### Database connectivity

For Docker:

```powershell
docker compose run --rm backend python -c "from app.db.session import get_engine; from sqlalchemy import text; connection = get_engine().connect(); print('Connected:', connection.execute(text('SELECT 1')).scalar()); connection.close()"
```

For a local backend, run from `backend/`:

```powershell
.\.venv\Scripts\python.exe -c "from app.db.session import get_engine; from sqlalchemy import text; connection = get_engine().connect(); print('Connected:', connection.execute(text('SELECT 1')).scalar()); connection.close()"
```

Success prints `Connected: 1`. The `/api/health` endpoint checks API liveness only; it does not verify database connectivity.

### Signup and sign-in

1. Open http://localhost:5173 and choose **Sign up**.
2. Enter your email, a password of at least 8 characters, confirm the password, and enter the signup code `defaultcode` (or your configured value).
3. Submit. Successful signup signs you in automatically.
4. Sign out, then sign in with the same email and password.

Passwords are stored as bcrypt hashes and may contain at most 72 UTF-8 bytes. JWT sessions expire after the configured interval (15 minutes by default); sign in again after expiry. Browser sign-out clears the stored token; it does not revoke an already issued token on the server.

### Checks

For local checks, run these in the respective application folders:

```powershell
# From backend/
.\.venv\Scripts\python.exe -m pytest tests -q

# From frontend/
npm.cmd run build
```

Backend authentication tests use an isolated SQLite test database by default; application accounts use PostgreSQL. Optional PostgreSQL tests use `AUTH_TEST_DATABASE_URL` and create temporary schemas, so use a dedicated test database with schema creation permissions.

## 5. Troubleshooting

| Symptom | What to check |
| --- | --- |
| Docker cannot connect to its engine | Start Docker Desktop and wait until the engine is ready. |
| Image pull fails with `lookup registry-1.docker.io: no such host` | Docker cannot resolve Docker Hub. Check internet/DNS, restart Docker Desktop, and configure Docker Desktop's proxy settings if your network requires a proxy. Retry `docker pull node:22-alpine` before rebuilding. |
| Port already allocated | Stop the existing process using port `5173` or `8000` before starting Compose. |
| Frontend shows backend unavailable | Check backend logs and http://localhost:8000/api/health. |
| Database unavailable / HTTP 503 | Check `DATABASE_URL`, the real Neon password, network access, and database initialization. |
| Authentication not configured / HTTP 503 | Set a random `JWT_SECRET` of at least 32 characters and restart/recreate the backend. |
| Invalid signup code | Enter the backend's current `SIGNUP_CODE`; recreate/restart the backend after changing it. |
| Authentication request times out | Authentication waits up to 30 seconds. Verify API and Neon connectivity. If signup timed out after submission, try signing in before retrying signup because the account may already have been created. |
| Account already exists | Use sign-in or a different email. |
| Changes are not reflected | Verify you are editing this repository and viewing the correct port; recreate services for `.env` changes. |
| A run stays queued | Start the local worker or check `docker compose logs worker`. |
| A run ends blocked | Expected until all five railway constraint modules are implemented. |

The current application supports health checks, authentication, CSV upload/validation, saved datasets, queued preparation jobs, network previews, run history, and reports. Solver orchestration, scoring expressions, CSV export, and validator integration are implemented, but railway constraints are deliberately pending and no feasible scheduling claim is made.
