from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from models.database import engine, Base
import models.evidence  # register all ORM models with Base

from routers import upload, analyze, result, report, verify

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


@app.get("/")
def root():
    return {"status": "TrustSphere AI backend running"}


@app.get("/health")
def health():
    return {"status": "ok"}
