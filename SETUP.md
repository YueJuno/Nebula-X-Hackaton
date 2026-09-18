# Development Setup

Run the React frontend and FastAPI backend either with Docker or directly on your computer. Both options use your hosted Neon PostgreSQL database.

All terminal examples use Windows PowerShell. Start in the repository root (`Nebula-X-Hackaton`) unless a section says otherwise.

## 1. Configure environment files

Keep backend and frontend configuration separate. Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env`, then replace the placeholders. If the files already exist, update the relevant settings without replacing your existing credentials.

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

## Scheduling workflow

1. Sign in and select the eight CSV files from `01_data/` (or a new instance using the same schema).
2. Choose scenario A, B, or C and click **Schedule scenario**.
3. The worker loads the instance, calculates spatial footprints, builds and solves the CP-SAT model, and exports the three submission CSVs.
4. Download the report and submission ZIP. A run is `completed` when the built-in validator finds no hard violations, or `needs_validation` when it finds some; the CSVs stay downloadable either way so the pinpoints can be inspected. See section 8.

Inputs, run metadata, and reports are stored in PostgreSQL and belong to the signed-in user. Current upload limits are 2 MB per CSV, 1,000 activities/locations, 260 weeks, and a bounded model size; oversized instances are rejected explicitly.

You can solve the public dataset without the web application or database. From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m scheduler ..\01_data --scenario A --submission-dir ..\04_solver_outputs\scenario_A --output ..\04_solver_outputs\scenario_A\report.json
```

The CP-SAT formulation is split into five constraint modules:

```text
backend/scheduler/constraints/workload.py
backend/scheduler/constraints/safety.py
backend/scheduler/constraints/possessions.py
backend/scheduler/constraints/contracts.py
backend/scheduler/constraints/eclo.py
```

Together they enforce workload delivery, release dates and predecessors; safety closures and buffers; possession mixes, co-sharing and capacity; weekly allocations and workfronts; deadlines, lateness and ECLO policy rules.

## 8. Validating a submission

The official scoring program is not included in the challenge pack, so the
repository ships its own implementation of the PS1 section 2.4 hard rules and
the section 2.7 report. Every solve is self-checked before its CSVs are offered
for download, and any submission folder can be checked on its own:

```powershell
.\.venv\Scripts\python.exe -m scheduler ..\01_data --check ..\04_solver_outputs\scenario_A
```

`--check` needs no OR-Tools and exits `0` when feasible, `2` otherwise, so it
drops straight into CI. It prints the full section 2.7 report plus a one-line
verdict such as `INFEASIBLE (week granularity): closure=65, co_share=14`.

| Module | Responsibility |
| --- | --- |
| `backend/scheduler/submission.py` | Parses the three submission CSVs; rejects a mixed-scenario `RESULTS.csv` |
| `backend/scheduler/rules.py` | The hard-rule checks, one function per section 2.4 rule |
| `backend/scheduler/scoring.py` | Soft scores and the section 2.5 objective |
| `backend/scheduler/validator.py` | Assembles the report; adapts an external validator when configured |

Rule tags: `workload`, `start_date`, `closure`, `mix`, `co_share`, `allocation`,
`workfront`, `eclo`, `eclo_window`, `capacity`, `planned_date`, `predecessor`,
`occupancy`, `results`, `format`.

### Buffer granularity

Section 2.4 rule 3 admits two readings, and no reference binary exists to settle
which one scoring uses, so `--granularity` selects it — for solving as well as
checking. **`week` is the default**, because a week-strict schedule satisfies
both readings; the web app exposes the same choice per run.

Measured on the public instance:

| Scenario | Week-strict objective | Per-possession objective | Feasible under both? |
| --- | ---: | ---: | --- |
| A | 123.2 | 25.2 | week-strict only |
| B | 40.0 | 30.0 | week-strict only |
| C | 36.1 | 25.2 | week-strict only |

Week-strict costs quality but is immune to however scoring resolves the rule;
the per-possession model scores better and produces 43-67 `closure` violations
if the strict reading is the one used. Since feasibility is a gate and score is
a margin, the repository ships week-strict and keeps the looser model available
for comparison. No Priority-1 contract overruns under either.

The two readings:

- `week` (default) — any two activities holding an access in the same week
  conflict when one's occupied span falls inside the other's closure. This is
  the conservative reading and matches the week-granular pinpoint in the
  section 2.7 example. Neither submitted field orders nights across contracts:
  `access_night` is explicitly local to a contract+type, and `co_share_group`
  is an arbitrary label.
- `possession` — only activities sharing a `co_share_group` in that week are
  treated as concurrent, reading rule 5's "separate possessions on separate
  nights" as a network-wide guarantee.

Co-sharing exempts a pair under either reading. Run both before submitting: a
schedule that is feasible only under `possession` is betting on the looser
interpretation.

Adding a run's interpretation to an existing database needs one statement, since
`python -m app.db.init_db` only creates missing tables:

```sql
ALTER TABLE scheduling_runs ADD COLUMN buffer_granularity VARCHAR(16) DEFAULT 'week';
```

## 9. Explaining a schedule

Producing a schedule is not the same as defending one. Two layers, separated by
how expensive they are:

```powershell
.\.venv\Scripts\python.exe -m scheduler ..\01_data --scenario A --explain
.\.venv\Scripts\python.exe -m scheduler ..\01_data --scenario A --unlocks 4
```

`--explain` attributes every overrunning activity to the weeks it could have
used but did not. It reads the solved schedule only, so it is cheap enough to
run inside a web request and is attached to every API run as
`report.explanation`. Blocking factors, in the order they dominate:

| Factor | Meaning |
| --- | --- |
| `window` | Planned start to deadline is shorter than the activity's workload, and an activity may take only one access-night a week. Structural — no contention relief can recover it. |
| `predecessor` | The preceding activity had not finished. |
| `allocation` | The contract's weekly access-night budget was already spent. |
| `workfront` | The contract held nights that week but had no free crew. |
| `capacity` | Locations on the activity's span were at nominal supply. |

`--unlocks N` goes further and re-solves the instance once per candidate lever,
ranking them by objective bought back. Levers are operational rather than
mathematical — one more access-night a week, one more workfront, one more
possession at a location, or an earlier mobilisation date — so each result is
something a planner can actually negotiate. Candidates are drawn from the
blocking factors and weighted by the delay cost they would relieve, so only
levers with evidence behind them are tried. This costs one solve per lever, so
it is a CLI/offline tool, not a request handler.

On the public instance, Scenario A's entire 25.2 objective is two structurally
impossible activities: `A036` needs 7 access-nights inside a 5-week window and
`A059` needs 7 inside 6 weeks. The lever sweep confirms it — pulling their
start dates forward recovers 18.2 and 7.0 respectively, while extra weekly
access buys nothing. This is also why Scenario B spends exactly 6 ECLO nights
(4 on `A036`, 2 on `A059`): that is the minimum needed to compress 7 units of
work into those windows at the 1.5x ECLO yield.

### External cross-check

When the official validator becomes available, configure `VALIDATOR_COMMAND` in
`backend/.env` as a JSON array of executable/arguments. The adapter replaces
`{instance_dir}` and `{submission_dir}` placeholders with temporary
directories, executes without a shell, and expects a JSON report on stdout with
a boolean `feasible` field. Its verdict appears alongside the built-in one, and
a run reaches `completed` only when the built-in validator passes and the
external one does not contradict it.

Spatial footprints currently assume a live closure reaching either interchange hub or its connecting sector triggers the cross-line closure. This interpretation and completion-date conventions still need checking against the official validator when it becomes available.

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
| A run ends `needs_validation` | The solver finished but the built-in validator found hard violations. Open the feasibility panel for the per-rule counts and pinpoints, or re-check the downloaded CSVs with `-m scheduler ..\01_data --check <dir>`. |

The application supports health checks, authentication, CSV upload/validation, saved datasets, queued solver jobs, network previews, run history, scenario-aware CP-SAT optimization, schedule metrics, CSV/ZIP export, and optional reference-validator integration.
