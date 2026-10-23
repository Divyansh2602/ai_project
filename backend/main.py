import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from models.database import engine, Base
import models.evidence  # register all ORM models with Base

from routers import upload, analyze, result, report, verify, history

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TrustSphere AI",
    description="Digital Forensics Framework for Synthetic Media Detection and Verification",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(analyze.router)
app.include_router(result.router)
app.include_router(report.router)
app.include_router(verify.router)
app.include_router(history.router)


# ── Web app ──────────────────────────────────────────────────────────
# Served by FastAPI itself, so one command starts the API and the UI and the UI is same-origin.
_HERE = os.path.dirname(os.path.abspath(__file__))
_STATIC = os.path.join(_HERE, "static")
_UPLOADS = os.path.join(_HERE, os.getenv("UPLOAD_DIR", "uploads"))

os.makedirs(_UPLOADS, exist_ok=True)
# Evidence files and the ELA / Grad-CAM heatmaps referenced by heatmap_path in the report.
app.mount("/uploads", StaticFiles(directory=_UPLOADS), name="uploads")
app.mount("/app", StaticFiles(directory=_STATIC, html=True), name="app")


@app.middleware("http")
async def _no_cache_app_shell(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/app"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@app.get("/")
def root():
    return RedirectResponse(url="/app/")


@app.get("/api")
def api_root():
    return {"status": "TrustSphere AI backend running"}


@app.get("/health")
def health():
    return {"status": "ok"}
