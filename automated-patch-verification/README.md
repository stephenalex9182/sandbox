# Automated Server Error Log Patch Verification Using E2B Sandboxes

PatchVerify is a FastAPI application with a vanilla JavaScript frontend. It parses Python/server logs, uses a structured LLM response to draft a unified diff, requires human approval, validates the diff, and runs the approved patch plus pytest inside a short-lived E2B sandbox. It never executes generated code on the API host. The sandbox has outbound internet disabled, receives no `.env`/secret files, and is always destroyed after execution.

## Requirements

- Python 3.11+
- Docker Desktop / Docker Engine for PostgreSQL
- OpenAI API key for root-cause analysis and patch generation
- E2B API key for sandbox verification
- Optional Google OAuth client credentials

## Setup and run

From this directory:

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
Copy-Item .env.example .env  # PowerShell; use `cp .env.example .env` elsewhere
```

Edit `.env` and set a random `JWT_SECRET` of at least 32 characters, `OPENAI_API_KEY`, and `E2B_API_KEY`. Start PostgreSQL:

```sh
docker compose up -d db
```

Run the app from the project directory:

```sh
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://localhost:8000](http://localhost:8000). `/api/health` reports whether AI and E2B credentials are configured. Registration requires a 12-character password. Google OAuth requires a Google OAuth web client with the exact redirect URI in `OAUTH_REDIRECT_URI`.

## Main flow

1. Register or sign in; optionally use Google OAuth.
2. Create a project and paste a traceback or log.
3. Review the parsed error and enter the relevant project files/tests as a JSON object. Only necessary files should be submitted; `.env`, `.git`, credentials, virtual environments, and secret paths are rejected.
4. Generate a structured AI patch. The proposed diff is checked for unified-diff structure, scope, path traversal, secret paths, and a 100 KB limit.
5. Approve or reject the diff. Only an approved patch can be sent to E2B.
6. The E2B VM receives the selected source files and diff, applies the patch, installs `requirements.txt` if present, runs pytest when tests are detected, captures output/exit status/duration, and is destroyed.
7. Failed attempts can produce a new AI patch up to three attempts. If no test suite exists, a successful run is reported as `partially_verified` with the required message: “Full verification unavailable because no test suite was detected.”

E2B networking is disabled to prevent sandbox code from accessing internal services or exfiltrating uploaded source. Consequently, dependencies not already present in the sandbox image cannot be downloaded at runtime; use an approved prebuilt E2B image with the project's dependencies when needed. This is an intentional security limit, not a claim that arbitrary dependencies were installed.

## API overview

All endpoints except health, register, login, and OAuth require `Authorization: Bearer <access_token>`.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register`, `/api/auth/login` | Create account / issue JWT |
| GET | `/api/auth/me` | Current account |
| GET, POST | `/api/projects` | List/create projects |
| GET, DELETE | `/api/projects/{id}` | Project details/delete |
| POST | `/api/logs/analyze` | Parse/analyze pasted log |
| POST | `/api/logs/upload?project_id={id}` | Upload `.txt` / `.log` |
| GET | `/api/logs/{id}` | Read analysis |
| POST | `/api/patches/draft` | Generate structured patch with source files |
| POST | `/api/patches/generate` | Save a supplied validated diff |
| GET | `/api/patches/{id}` | Read patch |
| POST | `/api/patches/{id}/approval?approved=true` | Human approval/rejection |
| POST | `/api/sandbox/verify` | Verify approved patch in E2B |
| GET | `/api/sandbox/{id}`, `/api/results/{id}` | Run details |
| GET | `/api/history` | Recent sandbox history |

Example register request:

```sh
curl -X POST http://localhost:8000/api/auth/register -H 'Content-Type: application/json' -d '{"email":"dev@example.com","password":"a-long-password-123"}'
```

Log analysis request (replace the project ID and bearer token):

```sh
curl -X POST http://localhost:8000/api/logs/analyze -H 'Authorization: Bearer TOKEN' -H 'Content-Type: application/json' -d '{"project_id":1,"content":"Traceback (most recent call last):\n  File \"app.py\", line 12, in run\nZeroDivisionError: division by zero"}'
```

Expected analysis includes `error_type`, `message`, `file`, `line`, `function`, `severity`, `timestamp`, and `root_cause`. Missing OpenAI configuration still permits log parsing, but AI patch generation returns HTTP 503 rather than fabricating a patch. Missing E2B configuration prevents execution and reports human review required.

## Environment variables

See `.env.example`. Secrets must be injected through environment variables; never commit `.env`. Limits include 200 KB per log, 1 MB per project file, 10 MB per project upload, 100 KB per patch, 120 seconds per sandbox by default, 200 KB captured per output stream, and at most three patch attempts.

## Verification checks

Run the small standard-library unit suite from the project directory:

```sh
python -m unittest discover -s tests -v
```

The sandbox runner performs the actual patch application and pytest execution only inside E2B. No patch is deployed or merged automatically. Human approval is a verification gate, not a production deployment action.

## Current scope

The UI accepts Python project files as JSON for this MVP rather than connecting to a repository provider. The PostgreSQL models include users, projects, error logs, patches, sandbox runs, and test results; schema creation is automatic for a fresh development database. Add Alembic migrations before applying model changes to an existing production database.
