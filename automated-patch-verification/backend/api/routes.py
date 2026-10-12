from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, func
import secrets
from urllib.parse import urlencode
import httpx
from backend.database.db import get_db
from backend.database.models import User, Project, ErrorLog, Patch, SandboxRun, TestResult
from backend.auth.security import hash_password, verify_password, create_token
from backend.auth.dependencies import current_user
from backend.config import get_settings
from backend.services.patch_validation import validate_diff
import logging

router = APIRouter(prefix="/api")
logger = logging.getLogger("patchverify.api")
class Register(BaseModel): email: EmailStr; password: str = Field(min_length=12, max_length=128)
class Login(BaseModel): email: EmailStr; password: str
class ProjectIn(BaseModel): name: str = Field(min_length=1, max_length=120); description: str = ""
class LogIn(BaseModel): project_id: int; content: str = Field(min_length=1, max_length=200_000)
class PatchIn(BaseModel): error_log_id: int; diff: str = Field(min_length=1, max_length=100_000); explanation: str = ""
class DraftIn(BaseModel): error_log_id: int; project_files: dict[str, str]; attempt: int = 1; previous_patch_id: int | None = None; failure_output: str = ""; exit_code: int | None = None
class VerifyIn(BaseModel): patch_id: int; project_files: dict[str, str]
def owned_project(db, user, project_id):
    p = db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == user.id))
    if not p: raise HTTPException(404, "Project not found.")
    return p

@router.post("/auth/register")
def register(body: Register, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)): raise HTTPException(409, "An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(body.password)); db.add(user); db.commit(); db.refresh(user)
    logger.info("user_registered user_id=%s", user.id)
    return {"access_token": create_token(user.id), "token_type": "bearer", "user": {"id": user.id, "email": user.email}}
@router.post("/auth/login")
def login(body: Login, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash): raise HTTPException(401, "Email or password is incorrect.")
    logger.info("user_login user_id=%s", user.id)
    return {"access_token": create_token(user.id), "token_type": "bearer", "user": {"id": user.id, "email": user.email}}
@router.get("/auth/me")
def me(user: User = Depends(current_user)): return {"id": user.id, "email": user.email}
@router.get("/auth/oauth/google")
def google_start():
    s = get_settings()
    if not s.google_client_id: raise HTTPException(503, "Google OAuth is not configured.")
    state = secrets.token_urlsafe(32)
    params = {"client_id": s.google_client_id, "redirect_uri": s.oauth_redirect_uri, "response_type": "code", "scope": "openid email profile", "state": state, "prompt": "select_account"}
    response = RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))
    response.set_cookie("oauth_state", state, httponly=True, secure=s.frontend_origin.startswith("https://"), samesite="lax", max_age=300)
    return response
@router.get("/auth/oauth/google/callback")
def google_callback(request: Request, code: str, state: str, db: Session = Depends(get_db)):
    s = get_settings()
    if not s.google_client_id or not s.google_client_secret: raise HTTPException(503, "Google OAuth is not configured.")
    if not request.cookies.get("oauth_state") or not secrets.compare_digest(request.cookies["oauth_state"], state): raise HTTPException(400, "OAuth state validation failed.")
    try:
        token_response = httpx.post("https://oauth2.googleapis.com/token", data={"code": code, "client_id": s.google_client_id, "client_secret": s.google_client_secret, "redirect_uri": s.oauth_redirect_uri, "grant_type": "authorization_code"}, timeout=10)
        token_response.raise_for_status()
        profile_response = httpx.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {token_response.json()['access_token']}"}, timeout=10)
        profile_response.raise_for_status(); profile = profile_response.json(); email = profile.get("email", "").lower()
        if not email or not profile.get("email_verified"): raise HTTPException(400, "Google did not return a verified email address.")
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(email=email, password_hash=None); db.add(user); db.commit(); db.refresh(user)
        response = RedirectResponse(s.frontend_origin.rstrip("/") + "/#access_token=" + create_token(user.id))
        response.delete_cookie("oauth_state", httponly=True, samesite="lax")
        return response
    except HTTPException: raise
    except Exception: raise HTTPException(502, "Google sign-in could not be completed.")
@router.get("/projects")
def projects(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [{"id": p.id, "name": p.name, "description": p.description, "created_at": p.created_at} for p in db.scalars(select(Project).where(Project.owner_id == user.id))]
@router.post("/projects")
def create_project(body: ProjectIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = Project(owner_id=user.id, name=body.name, description=body.description); db.add(p); db.commit(); db.refresh(p); logger.info("project_created user_id=%s project_id=%s", user.id, p.id); return {"id": p.id, "name": p.name, "description": p.description}
@router.get("/projects/{project_id}")
def project_detail(project_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = owned_project(db, user, project_id)
    return {"id": p.id, "name": p.name, "description": p.description, "logs": [{"id": l.id, "analysis": l.analysis, "status": l.status, "created_at": l.created_at} for l in p.error_logs]}
@router.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = owned_project(db, user, project_id); db.delete(p); db.commit(); return {"deleted": True}
def save_log(project_id, content, db):
    try:
        from backend.agents.analyzers import analyze_log
        analysis = analyze_log(content)
    except ValueError as e: raise HTTPException(422, str(e))
    except Exception: raise HTTPException(503, "Log analysis is unavailable. Check AI configuration and try again.")
    log = ErrorLog(project_id=project_id, content=content, analysis=analysis, status="analyzed"); db.add(log); db.commit(); db.refresh(log)
    return {"id": log.id, "analysis": analysis, "status": log.status}
@router.post("/logs/analyze")
def analyze(body: LogIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned_project(db, user, body.project_id); return save_log(body.project_id, body.content, db)
@router.post("/logs/upload")
def upload_log(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned_project(db, user, project_id)
    if file.filename and not file.filename.lower().endswith((".txt", ".log")): raise HTTPException(415, "Upload a .txt or .log file.")
    content = file.file.read(200_001).decode("utf-8", "replace")
    return save_log(project_id, content, db)
@router.get("/logs/{log_id}")
def get_log(log_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    l = db.get(ErrorLog, log_id)
    if not l: raise HTTPException(404, "Error log not found.")
    owned_project(db, user, l.project_id)
    return {"id": l.id, "analysis": l.analysis, "status": l.status, "created_at": l.created_at}
@router.post("/patches/generate")
def create_patch(body: PatchIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    log = db.get(ErrorLog, body.error_log_id)
    if not log: raise HTTPException(404, "Error log not found.")
    owned_project(db, user, log.project_id)
    try: scope = validate_diff(body.diff)
    except ValueError as e: raise HTTPException(422, str(e))
    p = Patch(error_log_id=log.id, diff=body.diff, explanation=body.explanation, status="awaiting_approval"); db.add(p); db.commit(); db.refresh(p)
    return {"id": p.id, "status": p.status, "scope": scope, "diff": p.diff, "explanation": p.explanation}
@router.post("/patches/draft")
def draft_patch(body: DraftIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    log = db.get(ErrorLog, body.error_log_id)
    if not log: raise HTTPException(404, "Error log not found.")
    owned_project(db, user, log.project_id); settings = get_settings()
    if body.attempt < 1 or body.attempt > min(settings.max_patch_attempts, 3): raise HTTPException(429, "Maximum patch attempts reached; human review is required.")
    if body.previous_patch_id:
        previous = db.get(Patch, body.previous_patch_id)
        if not previous or previous.error_log_id != log.id: raise HTTPException(404, "Previous patch not found.")
        if previous.attempt + 1 != body.attempt: raise HTTPException(409, "Retry attempt must follow the previous patch.")
        if previous.status != "failed": raise HTTPException(409, "Only a failed sandbox attempt can be retried.")
    try:
        from backend.sandbox.runner import _safe_files
        _safe_files(body.project_files)
        from backend.workflows.verification import build_draft_workflow
        analysis = log.analysis
        if body.failure_output: analysis["previous_failure"] = body.failure_output[:settings.max_output_bytes]
        flow = build_draft_workflow().invoke({"log": log.content, "analysis": analysis, "source_files": body.project_files, "failure_output": body.failure_output, "exit_code": body.exit_code, "patch": {"diff": previous.diff if body.previous_patch_id else ""}})
        draft = flow["patch"]; scope = flow["validation"]
        if set(scope["files"]) - set(draft.get("modified_files", [])): raise ValueError("Generated diff file list does not match its declared scope.")
        if set(scope["files"]) - set(body.project_files): raise ValueError("Patch targets a file that was not included in the supplied project source.")
    except ValueError as e: raise HTTPException(422, str(e))
    except RuntimeError as e: raise HTTPException(503, str(e))
    except Exception: raise HTTPException(503, "Patch generation failed. Check AI configuration and try again.")
    p = Patch(error_log_id=log.id, diff=draft["diff"], explanation=draft["explanation"], status="awaiting_approval", attempt=body.attempt); db.add(p); db.commit(); db.refresh(p)
    return {"id": p.id, "status": p.status, "attempt": p.attempt, "scope": scope, "diff": p.diff, "explanation": p.explanation, "test_recommendation": draft["test_recommendation"]}
@router.get("/patches/{patch_id}")
def get_patch(patch_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = db.get(Patch, patch_id)
    if not p: raise HTTPException(404, "Patch not found.")
    owned_project(db, user, p.error_log.project_id)
    return {"id": p.id, "diff": p.diff, "explanation": p.explanation, "status": p.status, "approved": p.approved, "attempt": p.attempt}
@router.post("/patches/{patch_id}/approval")
def approval(patch_id: int, approved: bool, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = db.get(Patch, patch_id)
    if not p: raise HTTPException(404, "Patch not found.")
    owned_project(db, user, p.error_log.project_id); p.approved = approved; p.status = "approved" if approved else "rejected"; db.commit()
    return {"id": p.id, "status": p.status, "approved": p.approved}
@router.post("/sandbox/verify")
def verify(body: VerifyIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = db.get(Patch, body.patch_id)
    if not p: raise HTTPException(404, "Patch not found.")
    owned_project(db, user, p.error_log.project_id)
    if not p.approved: raise HTTPException(409, "A human must approve this patch before sandbox verification.")
    try:
        scope = validate_diff(p.diff)
        if set(scope["files"]) - set(body.project_files): raise ValueError("Patch targets a file that was not included in the supplied project source.")
    except ValueError as e: raise HTTPException(422, str(e))
    run = SandboxRun(patch_id=p.id, status="running"); db.add(run); db.commit(); db.refresh(run)
    try:
        from backend.workflows.verification import build_verification_workflow
        result = build_verification_workflow().invoke({"source_files": body.project_files, "patch": {"diff": p.diff}})["result"]
        run.status = result["status"]; run.sandbox_id = result.get("sandbox_id"); run.stdout = result["stdout"]; run.stderr = result["stderr"]; run.exit_code = result["exit_code"]; run.duration_ms = result["duration_ms"]; counts = result.get("tests", {}); run.report = {"summary": result["report"], "tests": counts}
        if run.status == "failed" and p.attempt >= min(get_settings().max_patch_attempts, 3):
            run.status = "human_review_required"
            run.report["summary"] = "Maximum patch attempts reached; human review is required."
        p.status = run.status
        for test_status in ("passed", "failed", "skipped"):
            count = counts.get(test_status, 0)
            if count: db.add(TestResult(sandbox_run_id=run.id, name=f"pytest {test_status}", status=test_status, detail=f"{count} tests"))
    except Exception as e:
        logger.exception("sandbox_verification_failed run_id=%s patch_id=%s", run.id, p.id)
        run.status = "failed"; run.stderr = "Sandbox verification could not be completed. Check E2B configuration or server logs."; run.report = {"summary": "Verification could not be completed safely; human review is required."}; p.status = "human_review_required"
    db.commit(); db.refresh(run)
    return {"id": run.id, "patch_id": p.id, "status": run.status, "stdout": run.stdout, "stderr": run.stderr, "exit_code": run.exit_code, "duration_ms": run.duration_ms, "report": run.report, "attempt": p.attempt}
@router.get("/sandbox/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    run = db.get(SandboxRun, run_id)
    if not run: raise HTTPException(404, "Sandbox run not found.")
    owned_project(db, user, run.patch.error_log.project_id)
    return {"id": run.id, "status": run.status, "stdout": run.stdout, "stderr": run.stderr, "exit_code": run.exit_code, "duration_ms": run.duration_ms, "report": run.report, "attempt": run.patch.attempt}
@router.get("/results/{run_id}")
def result(run_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)): return get_run(run_id, db, user)
@router.get("/history")
def history(db: Session = Depends(get_db), user: User = Depends(current_user)):
    runs = db.scalars(select(SandboxRun).join(Patch).join(ErrorLog).join(Project).where(Project.owner_id == user.id).order_by(SandboxRun.created_at.desc()).limit(100))
    return [{"id": r.id, "status": r.status, "created_at": r.created_at, "patch_id": r.patch_id, "duration_ms": r.duration_ms, "exit_code": r.exit_code} for r in runs]
@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_ids = select(Project.id).where(Project.owner_id == user.id)
    counts = {
        "projects": db.scalar(select(func.count()).select_from(Project).where(Project.owner_id == user.id)) or 0,
        "errors": db.scalar(select(func.count()).select_from(ErrorLog).where(ErrorLog.project_id.in_(project_ids))) or 0,
        "patches": db.scalar(select(func.count()).select_from(Patch).join(ErrorLog).where(ErrorLog.project_id.in_(project_ids))) or 0,
        "verified": db.scalar(select(func.count()).select_from(Patch).join(ErrorLog).where(ErrorLog.project_id.in_(project_ids), Patch.status == "verified")) or 0,
        "failed": db.scalar(select(func.count()).select_from(Patch).join(ErrorLog).where(ErrorLog.project_id.in_(project_ids), Patch.status.in_(["failed", "human_review_required"]))) or 0,
    }
    runs = db.scalars(select(SandboxRun).join(Patch).join(ErrorLog).join(Project).where(Project.owner_id == user.id).order_by(SandboxRun.created_at.desc()).limit(6))
    recent = [{"id": r.id, "status": r.status, "created_at": r.created_at, "patch_id": r.patch_id, "duration_ms": r.duration_ms, "exit_code": r.exit_code} for r in runs]
    return {**counts, "recent_runs": recent}
