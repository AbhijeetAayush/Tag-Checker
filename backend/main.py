"""Tag Checker API — minimal FastAPI entry for ECS/ALB health checks."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Tag Checker API", version="0.1.0")

# Browser calls from Vercel: set ALLOWED_ORIGINS in ECS task env (comma-separated),
# e.g. https://tag-checker-xxx.vercel.app — or "*" for demos only.
_raw = os.getenv("ALLOWED_ORIGINS", "*").strip()
_origins = [x.strip() for x in _raw.split(",") if x.strip()] or ["*"]
# allow_credentials + wildcard origin is invalid per CORS spec
_creds = "*" not in _origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "tag-checker-api", "docs": "/docs"}
