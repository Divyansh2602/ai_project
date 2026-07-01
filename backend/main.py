from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="TrustSphere AI",
    description="Digital Forensics Framework for Synthetic Media Detection and Verification",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "TrustSphere AI backend running"}

@app.get("/health")
def health():
    return {"status": "ok"}
