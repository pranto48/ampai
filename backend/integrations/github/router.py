from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .service import GitHubIntegrationService

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
