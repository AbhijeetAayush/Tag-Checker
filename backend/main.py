"""Tag Checker API — FastAPI backend for Tag Inspector MVP."""

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from db import engine, get_db
from models import AuditRun, Base, RunStatus, Site
from runner import InProcessRunner, serialize_run_config
from schemas import RunCreate, RunOut, SiteCreate, SiteOut, SiteUpdate

_runner = InProcessRunner()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Create tables (MVP). For production, prefer Alembic migrations.
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _runner.start()
    yield
    _runner.stop()


app = FastAPI(title="Tag Checker API", version="0.2.0", lifespan=lifespan)

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


@app.post("/sites", response_model=SiteOut, status_code=201)
def create_site(payload: SiteCreate) -> SiteOut:
    with get_db() as db:
        site = Site(name=payload.name.strip(), base_url=str(payload.base_url).rstrip("/"))
        db.add(site)
        db.commit()
        db.refresh(site)
        return SiteOut.model_validate(site)


@app.get("/sites", response_model=list[SiteOut])
def list_sites() -> list[SiteOut]:
    with get_db() as db:
        rows = db.execute(select(Site).order_by(Site.created_at.desc())).scalars().all()
        return [SiteOut.model_validate(r) for r in rows]


@app.get("/sites/{site_id}", response_model=SiteOut)
def get_site(site_id: str) -> SiteOut:
    with get_db() as db:
        site = db.get(Site, site_id)
        if not site:
            raise HTTPException(status_code=404, detail="site not found")
        return SiteOut.model_validate(site)


@app.patch("/sites/{site_id}", response_model=SiteOut)
def update_site(site_id: str, payload: SiteUpdate) -> SiteOut:
    with get_db() as db:
        site = db.get(Site, site_id)
        if not site:
            raise HTTPException(status_code=404, detail="site not found")
        if payload.name is not None:
            site.name = payload.name.strip()
        if payload.base_url is not None:
            site.base_url = str(payload.base_url).rstrip("/")
        db.commit()
        db.refresh(site)
        return SiteOut.model_validate(site)


@app.delete("/sites/{site_id}", status_code=204)
def delete_site(site_id: str) -> None:
    with get_db() as db:
        site = db.get(Site, site_id)
        if not site:
            raise HTTPException(status_code=404, detail="site not found")
        db.delete(site)
        db.commit()


def _run_to_out(run: AuditRun) -> RunOut:
    config: dict[str, Any]
    try:
        import json

        config = json.loads(run.config_json or "{}")
    except Exception:
        config = {}

    return RunOut(
        id=run.id,
        site_id=run.site_id,
        status=run.status.value if isinstance(run.status, RunStatus) else str(run.status),
        trigger=run.trigger,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        pages_done=run.pages_done,
        pages_total_estimate=run.pages_total_estimate,
        config=config,
        error_code=run.error_code,
        error_message=run.error_message,
    )


@app.post("/sites/{site_id}/runs", response_model=RunOut, status_code=202)
def start_run(site_id: str, payload: RunCreate) -> RunOut:
    with get_db() as db:
        site = db.get(Site, site_id)
        if not site:
            raise HTTPException(status_code=404, detail="site not found")

        config = payload.model_dump(exclude_none=True)
        pages_total = config.get("max_pages") or 5
        run = AuditRun(
            site_id=site.id,
            status=RunStatus.queued,
            trigger=payload.trigger,
            pages_done=0,
            pages_total_estimate=min(int(pages_total), 10000),
            config_json=serialize_run_config(config),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return _run_to_out(run)


@app.get("/sites/{site_id}/runs", response_model=list[RunOut])
def list_runs(site_id: str, limit: int = 20) -> list[RunOut]:
    limit = max(1, min(limit, 200))
    with get_db() as db:
        site = db.get(Site, site_id)
        if not site:
            raise HTTPException(status_code=404, detail="site not found")
        runs = (
            db.execute(select(AuditRun).where(AuditRun.site_id == site_id).order_by(AuditRun.created_at.desc()).limit(limit))
            .scalars()
            .all()
        )
        return [_run_to_out(r) for r in runs]


@app.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str) -> RunOut:
    with get_db() as db:
        run = db.get(AuditRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        return _run_to_out(run)


@app.post("/runs/{run_id}/cancel", response_model=RunOut)
def cancel_run(run_id: str) -> RunOut:
    with get_db() as db:
        run = db.get(AuditRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        if run.status in (RunStatus.succeeded, RunStatus.failed, RunStatus.cancelled):
            return _run_to_out(run)
        run.status = RunStatus.cancelled
        from datetime import datetime, timezone

        run.finished_at = run.finished_at or datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        return _run_to_out(run)
