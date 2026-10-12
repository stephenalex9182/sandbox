import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.api.routes import router
from backend.database.db import Base, engine
from backend.database import models  # noqa: F401
from backend.config import get_settings
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
settings = get_settings(); app = FastAPI(title="PatchVerify AI", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=True, allow_methods=["GET", "POST", "DELETE"], allow_headers=["Authorization", "Content-Type"])
Base.metadata.create_all(bind=engine); app.include_router(router)
@app.get("/api/health")
def health(): return {"status": "ok", "sandbox_configured": bool(settings.e2b_api_key), "ai_configured": bool(settings.openai_api_key)}
frontend = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
