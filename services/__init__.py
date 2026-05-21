"""Service layer package.

This package is the target location for business logic currently embedded
in route modules.
"""

from .repo_edit_orchestrator import (
    EditPlan,
    OrchestratorJob,
    PatchHunk,
    RepoEditOrchestrator,
    RepoTargetContext,
)
from .web_search_service import (
    SearchHit,
    WebSearchResult,
    WebSearchService,
)
from .terminal_service import (
    CommandBlockedError,
    CommandResult,
    TerminalConfig,
    TerminalConfirmationRequired,
    TerminalDisabledError,
    TerminalService,
)
from .browser_automation_service import (
    BrowserActionResult,
    BrowserActionStatus,
    BrowserAutomationService,
    BrowserConfig,
    BrowserConfirmationDeniedError,
    BrowserDisabledError,
    BrowserForbiddenOperationError,
    BrowserTimeoutError,
)
from .backup_service import (
    BackupManifest,
    BackupProfile,
    BackupResult,
    BackupService,
    PreflightCheck,
    PreflightResult,
    RestoreResult,
)

__all__ = [
    "EditPlan",
    "OrchestratorJob",
    "PatchHunk",
    "RepoEditOrchestrator",
    "RepoTargetContext",
    "SearchHit",
    "WebSearchResult",
    "WebSearchService",
    "CommandBlockedError",
    "CommandResult",
    "TerminalConfig",
    "TerminalConfirmationRequired",
    "TerminalDisabledError",
    "TerminalService",
    "BrowserActionResult",
    "BrowserActionStatus",
    "BrowserAutomationService",
    "BrowserConfig",
    "BrowserConfirmationDeniedError",
    "BrowserDisabledError",
    "BrowserForbiddenOperationError",
    "BrowserTimeoutError",
    "BackupManifest",
    "BackupProfile",
    "BackupResult",
    "BackupService",
    "PreflightCheck",
    "PreflightResult",
    "RestoreResult",
]
