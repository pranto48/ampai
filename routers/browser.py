"""Browser Automation router: endpoints under /api/browser/.

Provides endpoints for browser automation actions (open, navigate, search,
click, type, submit, extract, screenshot, close), job listing, and
admin-only domain allowlist management.

Requirements: 8.11
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, insert, desc

from core.audit import ACTION_BROWSER_ACTION, ACTION_BROWSER_NAVIGATE, AuditLogger
from core.deps import UserContext, require_admin_user, require_authenticated_user
from database import automation_jobs, engine as db_engine, get_config, set_config
from policy.browser_policy import BrowserPolicy
from services.browser_automation_service import (
    BrowserActionResult,
    BrowserActionStatus,
    BrowserAutomationService,
    BrowserConfig,
    BrowserDisabledError,
    BrowserForbiddenOperationError,
    BrowserTimeoutError,
)

router = APIRouter(tags=["browser"])


# ── Request models ────────────────────────────────────────────────────────────


class BrowserOpenRequest(BaseModel):
    """Request body for POST /api/browser/open."""
    pass


class BrowserNavigateRequest(BaseModel):
    """Request body for POST /api/browser/navigate."""
    url: str = Field(..., min_length=1, max_length=2048)
    wait_for: Optional[str] = None


class BrowserSearchRequest(BaseModel):
    """Request body for POST /api/browser/search."""
    query: str = Field(..., min_length=1, max_length=500)
    engine: Optional[str] = Field(default="google", max_length=50)


class BrowserClickRequest(BaseModel):
    """Request body for POST /api/browser/click."""
    selector: str = Field(..., min_length=1, max_length=500)


class BrowserTypeRequest(BaseModel):
    """Request body for POST /api/browser/type."""
    selector: str = Field(..., min_length=1, max_length=500)
    value: str = Field(..., max_length=5000)
    credentials_provided: bool = False


class BrowserSubmitRequest(BaseModel):
    """Request body for POST /api/browser/submit."""
    selector: str = Field(..., min_length=1, max_length=500)


class BrowserExtractRequest(BaseModel):
    """Request body for POST /api/browser/extract."""
    selector: Optional[str] = Field(default=None, max_length=500)


class BrowserScreenshotRequest(BaseModel):
    """Request body for POST /api/browser/screenshot."""
    full_page: bool = False


class BrowserCloseRequest(BaseModel):
    """Request body for POST /api/browser/close."""
    pass


class AllowlistUpdateRequest(BaseModel):
    """Request body for POST /api/browser/allowlist."""
    domains: List[str] = Field(..., max_length=200)


# ── Response models ───────────────────────────────────────────────────────────


class BrowserActionResponse(BaseModel):
    """Standard response for browser action endpoints."""
    action: str
    status: str
    message: str = ""
    data: Optional[Any] = None
    url: Optional[str] = None
    timestamp: str = ""
    duration_ms: int = 0


class AutomationJobResponse(BaseModel):
    """Response for a single automation job."""
    id: int
    job_type: str
    status: str
    request: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    finished_at: Optional[str] = None


class AutomationJobsListResponse(BaseModel):
    """Response for GET /api/browser/jobs."""
    jobs: List[AutomationJobResponse] = []
    total: int = 0


class AllowlistResponse(BaseModel):
    """Response for GET /api/browser/allowlist."""
    domains: List[str] = []


# ── Service helpers ───────────────────────────────────────────────────────────

# Config key for storing the domain allowlist in app_configs
_ALLOWLIST_CONFIG_KEY = "browser_domain_allowlist"


def _get_domain_allowlist() -> List[str]:
    """Load domain allowlist from app_configs or env var."""
    stored = get_config(_ALLOWLIST_CONFIG_KEY)
    if stored:
        try:
            return json.loads(stored)
        except (json.JSONDecodeError, TypeError):
            pass
    # Fallback to env var
    env_val = os.getenv("BROWSER_DOMAIN_ALLOWLIST", "")
    if env_val:
        return [d.strip() for d in env_val.split(",") if d.strip()]
    return []


def _get_browser_service() -> BrowserAutomationService:
    """Create a BrowserAutomationService with current config."""
    domain_allowlist = _get_domain_allowlist()
    config = BrowserConfig(
        enabled=os.getenv("BROWSER_AUTOMATION_ENABLED", "false").lower() == "true",
        headless=os.getenv("BROWSER_HEADLESS", "false").lower() == "true",
        domain_allowlist=domain_allowlist,
    )
    audit_logger = AuditLogger(engine=db_engine)
    policy = BrowserPolicy(domain_allowlist)
    return BrowserAutomationService(
        config=config,
        audit_logger=audit_logger,
        browser_policy=policy,
    )


def _result_to_response(result: BrowserActionResult) -> BrowserActionResponse:
    """Convert a BrowserActionResult dataclass to a response model."""
    return BrowserActionResponse(
        action=result.action,
        status=result.status,
        message=result.message,
        data=result.data,
        url=result.url,
        timestamp=result.timestamp,
        duration_ms=result.duration_ms,
    )


def _record_job(
    username: str,
    job_type: str,
    request_data: Optional[Dict[str, Any]],
    result_data: Optional[Dict[str, Any]],
    job_status: str = "completed",
) -> None:
    """Record an automation job in the automation_jobs table."""
    if not db_engine:
        return
    try:
        with db_engine.connect() as conn:
            conn.execute(
                insert(automation_jobs).values(
                    username=username,
                    job_type=job_type,
                    status=job_status,
                    request=request_data,
                    result=result_data,
                    created_at=datetime.now(timezone.utc),
                    finished_at=datetime.now(timezone.utc) if job_status in ("completed", "failed") else None,
                )
            )
            conn.commit()
    except Exception:
        pass  # Non-critical: don't fail the action if job recording fails


# ── Browser action endpoints ──────────────────────────────────────────────────


@router.post("/api/browser/open", response_model=BrowserActionResponse)
async def browser_open(
    request: BrowserOpenRequest = BrowserOpenRequest(),
    current_user: UserContext = Depends(require_authenticated_user),
) -> BrowserActionResponse:
    """Open a browser instance."""
    service = _get_browser_service()
    try:
        result = await service.open_browser(
            username=current_user.username,
        )
    except BrowserDisabledError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Browser automation is disabled. An admin must enable it.",
        )

    _record_job(
        username=current_user.username,
        job_type="open",
        request_data=None,
        result_data={"status": result.status, "message": result.message},
        job_status="completed" if result.status == BrowserActionStatus.SUCCESS else "failed",
    )
    return _result_to_response(result)


@router.post("/api/browser/navigate", response_model=BrowserActionResponse)
async def browser_navigate(
    request: BrowserNavigateRequest,
    current_user: UserContext = Depends(require_authenticated_user),
) -> BrowserActionResponse:
    """Navigate to a URL (domain allowlist enforced)."""
    service = _get_browser_service()
    try:
        result = await service.navigate(
            url=request.url,
            username=current_user.username,
        )
    except BrowserDisabledError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Browser automation is disabled. An admin must enable it.",
        )

    _record_job(
        username=current_user.username,
        job_type="navigate",
        request_data={"url": request.url},
        result_data={"status": result.status, "message": result.message},
        job_status="completed" if result.status == BrowserActionStatus.SUCCESS else "failed",
    )
    return _result_to_response(result)


@router.post("/api/browser/search", response_model=BrowserActionResponse)
async def browser_search(
    request: BrowserSearchRequest,
    current_user: UserContext = Depends(require_authenticated_user),
) -> BrowserActionResponse:
    """Search via browser (navigates to search engine with query)."""
    service = _get_browser_service()

    # Build search URL based on engine
    search_urls = {
        "google": "https://www.google.com/search?q=",
        "bing": "https://www.bing.com/search?q=",
        "duckduckgo": "https://duckduckgo.com/?q=",
    }
    engine = (request.engine or "google").lower()
    base_url = search_urls.get(engine, search_urls["google"])
    search_url = base_url + request.query.replace(" ", "+")

    try:
        result = await service.navigate(
            url=search_url,
            username=current_user.username,
        )
        # Override action name to "search" for clarity
        result.action = "search"
    except BrowserDisabledError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Browser automation is disabled. An admin must enable it.",
        )

    _record_job(
        username=current_user.username,
        job_type="search",
        request_data={"query": request.query, "engine": engine},
        result_data={"status": result.status, "message": result.message},
        job_status="completed" if result.status == BrowserActionStatus.SUCCESS else "failed",
    )
    return _result_to_response(result)


@router.post("/api/browser/click", response_model=BrowserActionResponse)
async def browser_click(
    request: BrowserClickRequest,
    current_user: UserContext = Depends(require_authenticated_user),
) -> BrowserActionResponse:
    """Click an element by CSS selector."""
    service = _get_browser_service()
    try:
        result = await service.click(
            selector=request.selector,
            username=current_user.username,
        )
    except BrowserDisabledError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Browser automation is disabled. An admin must enable it.",
        )
    except BrowserForbiddenOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )

    _record_job(
        username=current_user.username,
        job_type="click",
        request_data={"selector": request.selector},
        result_data={"status": result.status, "message": result.message},
        job_status="completed" if result.status == BrowserActionStatus.SUCCESS else "failed",
    )
    return _result_to_response(result)


@router.post("/api/browser/type", response_model=BrowserActionResponse)
async def browser_type(
    request: BrowserTypeRequest,
    current_user: UserContext = Depends(require_authenticated_user),
) -> BrowserActionResponse:
    """Type text into an element by CSS selector."""
    service = _get_browser_service()
    try:
        result = await service.type_text(
            selector=request.selector,
            text=request.value,
            username=current_user.username,
            credentials_provided=request.credentials_provided,
        )
    except BrowserDisabledError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Browser automation is disabled. An admin must enable it.",
        )
    except BrowserForbiddenOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )

    _record_job(
        username=current_user.username,
        job_type="type",
        request_data={"selector": request.selector, "value_length": len(request.value)},
        result_data={"status": result.status, "message": result.message},
        job_status="completed" if result.status == BrowserActionStatus.SUCCESS else "failed",
    )
    return _result_to_response(result)


@router.post("/api/browser/submit", response_model=BrowserActionResponse)
async def browser_submit(
    request: BrowserSubmitRequest,
    current_user: UserContext = Depends(require_authenticated_user),
) -> BrowserActionResponse:
    """Submit a form by CSS selector."""
    service = _get_browser_service()
    try:
        result = await service.submit_form(
            selector=request.selector,
            username=current_user.username,
        )
    except BrowserDisabledError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Browser automation is disabled. An admin must enable it.",
        )
    except BrowserForbiddenOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )

    _record_job(
        username=current_user.username,
        job_type="submit",
        request_data={"selector": request.selector},
        result_data={"status": result.status, "message": result.message},
        job_status="completed" if result.status == BrowserActionStatus.SUCCESS else "failed",
    )
    return _result_to_response(result)


@router.post("/api/browser/extract", response_model=BrowserActionResponse)
async def browser_extract(
    request: BrowserExtractRequest = BrowserExtractRequest(),
    current_user: UserContext = Depends(require_authenticated_user),
) -> BrowserActionResponse:
    """Extract page content (text or specific element)."""
    service = _get_browser_service()
    try:
        result = await service.extract(
            username=current_user.username,
            selector=request.selector,
        )
    except BrowserDisabledError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Browser automation is disabled. An admin must enable it.",
        )
    except BrowserForbiddenOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )

    _record_job(
        username=current_user.username,
        job_type="extract",
        request_data={"selector": request.selector},
        result_data={"status": result.status, "message": result.message},
        job_status="completed" if result.status == BrowserActionStatus.SUCCESS else "failed",
    )
    return _result_to_response(result)


@router.post("/api/browser/screenshot", response_model=BrowserActionResponse)
async def browser_screenshot(
    request: BrowserScreenshotRequest = BrowserScreenshotRequest(),
    current_user: UserContext = Depends(require_authenticated_user),
) -> BrowserActionResponse:
    """Take a screenshot of the current page."""
    service = _get_browser_service()
    try:
        result = await service.screenshot(
            username=current_user.username,
            full_page=request.full_page,
        )
    except BrowserDisabledError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Browser automation is disabled. An admin must enable it.",
        )

    _record_job(
        username=current_user.username,
        job_type="screenshot",
        request_data={"full_page": request.full_page},
        result_data={"status": result.status, "message": result.message},
        job_status="completed" if result.status == BrowserActionStatus.SUCCESS else "failed",
    )
    return _result_to_response(result)


@router.post("/api/browser/close", response_model=BrowserActionResponse)
async def browser_close(
    request: BrowserCloseRequest = BrowserCloseRequest(),
    current_user: UserContext = Depends(require_authenticated_user),
) -> BrowserActionResponse:
    """Close the browser instance."""
    service = _get_browser_service()
    try:
        result = await service.close(
            username=current_user.username,
        )
    except BrowserDisabledError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Browser automation is disabled. An admin must enable it.",
        )

    _record_job(
        username=current_user.username,
        job_type="close",
        request_data=None,
        result_data={"status": result.status, "message": result.message},
        job_status="completed" if result.status == BrowserActionStatus.SUCCESS else "failed",
    )
    return _result_to_response(result)


# ── Job listing endpoint ──────────────────────────────────────────────────────


@router.get("/api/browser/jobs", response_model=AutomationJobsListResponse)
def list_browser_jobs(
    limit: int = 50,
    offset: int = 0,
    current_user: UserContext = Depends(require_authenticated_user),
) -> AutomationJobsListResponse:
    """List automation jobs for the current user."""
    if not db_engine:
        return AutomationJobsListResponse(jobs=[], total=0)

    try:
        with db_engine.connect() as conn:
            # Count total
            from sqlalchemy import func
            count_stmt = select(func.count()).select_from(automation_jobs).where(
                automation_jobs.c.username == current_user.username
            )
            total = conn.execute(count_stmt).scalar() or 0

            # Fetch jobs
            stmt = (
                select(automation_jobs)
                .where(automation_jobs.c.username == current_user.username)
                .order_by(desc(automation_jobs.c.created_at))
                .limit(min(limit, 200))
                .offset(offset)
            )
            rows = conn.execute(stmt).fetchall()

            jobs = []
            for row in rows:
                jobs.append(AutomationJobResponse(
                    id=row.id,
                    job_type=row.job_type,
                    status=row.status,
                    request=row.request,
                    result=row.result,
                    created_at=row.created_at.isoformat() if row.created_at else None,
                    finished_at=row.finished_at.isoformat() if row.finished_at else None,
                ))

            return AutomationJobsListResponse(jobs=jobs, total=total)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve jobs: {str(exc)[:200]}",
        )


# ── Admin allowlist endpoints ─────────────────────────────────────────────────


@router.get("/api/browser/allowlist", response_model=AllowlistResponse)
def get_allowlist(
    current_user: UserContext = Depends(require_admin_user),
) -> AllowlistResponse:
    """Get the current domain allowlist (admin only)."""
    domains = _get_domain_allowlist()
    return AllowlistResponse(domains=domains)


@router.post("/api/browser/allowlist", response_model=AllowlistResponse)
def update_allowlist(
    request: AllowlistUpdateRequest,
    current_user: UserContext = Depends(require_admin_user),
) -> AllowlistResponse:
    """Update the domain allowlist (admin only)."""
    # Normalize domains
    cleaned = [d.lower().strip() for d in request.domains if d.strip()]

    # Persist to app_configs
    set_config(_ALLOWLIST_CONFIG_KEY, json.dumps(cleaned))

    # Log the change
    audit = AuditLogger(engine=db_engine)
    audit.log(
        username=current_user.username,
        action_type=ACTION_BROWSER_ACTION,
        details={
            "action": "update_allowlist",
            "domains": cleaned,
            "domain_count": len(cleaned),
        },
        category="browser",
    )

    return AllowlistResponse(domains=cleaned)
