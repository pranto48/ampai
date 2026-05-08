from typing import Optional
import uuid

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from audit.records import list_activity_report
from observability.metrics import METRICS
from .service import GitHubIntegrationService
from backend.jobs_repo_edit import manager, stream_events

router = APIRouter(tags=["github"])


class ConnectRequest(BaseModel):
    mode: str = "app"
    installation_id: Optional[int] = None
    access_token: Optional[str] = None
    scopes: list[str] = []


class RepoSelectionRequest(BaseModel):
    owner: str
    repo: str


@router.post("/github/connect")
def github_connect(req: ConnectRequest):
    service = GitHubIntegrationService()
    if req.mode not in {"app", "oauth"}:
        raise HTTPException(status_code=400, detail="mode must be app or oauth")
    if req.mode == "app" and not req.installation_id:
        raise HTTPException(status_code=400, detail="installation_id required for app mode")
    if not req.access_token:
        raise HTTPException(status_code=400, detail="access_token is required")
    service.save_connection(req.mode, installation_id=req.installation_id, token=req.access_token, scopes=req.scopes)
    return {"ok": True, "mode": req.mode, "storage": "encrypted"}


@router.get("/github/repos")
def github_repos():
    service = GitHubIntegrationService()
    try:
        repos = service.list_repos()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"repos": repos}


@router.post("/github/repo/select")
def github_repo_select(req: RepoSelectionRequest):
    service = GitHubIntegrationService()
    try:
        caps = service.repo_capabilities(req.owner, req.repo)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"selected": {"owner": req.owner, "repo": req.repo}, "capabilities": caps}


class RepoEditRequest(BaseModel):
    github_token: str
    instruction: str
    context: dict
    max_attempts: int = 4


@router.post("/github/repo-edit/jobs")
def enqueue_repo_edit(req: RepoEditRequest, idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    job = manager.enqueue(req.model_dump(), idempotency_key=idempotency_key)
    return {"job_id": job["id"], "status": job["status"], "idempotency_key": idempotency_key}


@router.get("/github/repo-edit/jobs/{job_id}")
def get_repo_edit_job(job_id: str):
    job = manager.store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": job}


@router.post("/github/repo-edit/jobs/{job_id}/cancel")
def cancel_repo_edit_job(job_id: str):
    job = manager.cancel(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": job}


@router.get("/github/repo-edit/jobs/{job_id}/events")
def stream_repo_edit_job(job_id: str):
    if not manager.store.get_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return StreamingResponse(stream_events(job_id), media_type="text/event-stream")
