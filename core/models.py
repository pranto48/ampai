"""All Pydantic request and response models for AmpAI routers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# ── Attachments / Chat ────────────────────────────────────────────────────────


class Attachment(BaseModel):
    filename: str
    url: str
    type: str
    extracted_text: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: str
    message: str
    model_type: str = "ollama"
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    memory_mode: str = "indexed"
    memory_top_k: Optional[int] = 5
    memory_recency_bias: float = 0.0
    memory_category_filter: Optional[str] = ""
    persona_id: Optional[str] = None
    use_web_search: bool = False
    enable_browser_tools: bool = False
    enable_terminal_tools: bool = False
    attachments: List[Attachment] = []
    recency_bias: Optional[float] = None
    category_filter: Optional[str] = None
    chat_output_mode: Optional[str] = None


# ── Memory ────────────────────────────────────────────────────────────────────


class MemoryInboxUpdateRequest(BaseModel):
    status: str
    edited_text: Optional[str] = None


class CuratorNudgeAckRequest(BaseModel):
    nudge_id: int


class MemoryPolicyRequest(BaseModel):
    auto_capture_enabled: bool = True
    require_approval: bool = True
    pii_strict_mode: bool = True
    retention_days: int = 365
    allowed_categories: List[str] = []


class MemoryPolicyUpdateRequest(BaseModel):
    auto_capture_enabled: bool = True
    require_approval: bool = False
    pii_strict_mode: bool = False
    retention_days: int = 365
    allowed_categories: List[str] = []


class MemoryExplorerQuery(BaseModel):
    query: Optional[str] = ""
    category: Optional[str] = ""
    owner_scope: Optional[str] = "mine"  # mine|shared|all
    date_from: Optional[str] = ""
    date_to: Optional[str] = ""
    limit: int = 50
    offset: int = 0


class MemoryGroupCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    members: List[str] = []


class MemoryGroupShareRequest(BaseModel):
    session_id: str


# ── Skills ────────────────────────────────────────────────────────────────────


class SkillSynthesisRequest(BaseModel):
    session_id: str
    min_messages: int = 4
    auto_activate_threshold: float = 0.8


class SkillStatusUpdateRequest(BaseModel):
    status: str


class SkillRunRequest(BaseModel):
    skill_id: int
    skill_version_id: Optional[int] = None
    session_id: Optional[str] = None
    status: str = "success"
    latency_ms: Optional[int] = None
    user_feedback: Optional[int] = None
    notes: Optional[str] = None


class SkillOptimizeRequest(BaseModel):
    lookback_days: int = 14
    min_runs: int = 5
    success_threshold: float = 0.7
    canary_fraction: float = 0.2


# Skill engine models (autonomous agent section)
class SkillCreateRequest(BaseModel):
    name: str
    description: str = ""
    system_prompt: str
    trigger_pattern: str = ""
    parameters: Optional[Dict[str, Any]] = None
    tags: str = ""


class SkillUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    trigger_pattern: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    tags: Optional[str] = None
    status: Optional[str] = None
    safety_level: Optional[str] = None


class SkillExecuteRequest(BaseModel):
    user_message: str
    session_id: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    model_type: str = "ollama"


class SkillAutoCreateRequest(BaseModel):
    session_id: str
    skill_name: str
    description: str = ""
    model_type: str = "ollama"


# ── Recall ────────────────────────────────────────────────────────────────────


class RecallSearchRequest(BaseModel):
    q: str
    session_id: Optional[str] = None
    limit: int = 20


class RecallHybridSearchRequest(BaseModel):
    q: str
    session_id: Optional[str] = None
    limit: int = 20
    lexical_weight: float = 0.35
    semantic_weight: float = 0.55
    recency_weight: float = 0.10


class RecallQueryRequest(BaseModel):
    query: str
    limit: int = 20
    use_llm: bool = True
    model_type: str = "ollama"


# ── Integrations ──────────────────────────────────────────────────────────────


class TelegramIntegrationSaveRequest(BaseModel):
    bot_token: str = ""
    webhook_url: str = ""
    secret_token: Optional[str] = None
    enabled: bool = False


class EmailSummaryRequest(BaseModel):
    model_type: str = "ollama"
    api_key: Optional[str] = None
    session_id: str = "system_email_reports"


class EmailSummaryTodayRequest(BaseModel):
    provider: str = "outlook"
    timezone: str = "UTC"
    max_results: int = 50
    model_type: str = "ollama"
    model_name: Optional[str] = None
    api_key: Optional[str] = None


# ── Personas ──────────────────────────────────────────────────────────────────


class PersonaCreateRequest(BaseModel):
    name: str
    system_prompt: str
    tags: List[str] = []
    is_default: bool = False
    is_global: bool = False


class PersonaUpdateRequest(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    tags: Optional[List[str]] = None
    is_default: Optional[bool] = None


# ── Workspaces ────────────────────────────────────────────────────────────────


class WorkspaceCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    members: List[Dict[str, str]] = []


class WorkspaceMemberUpdateRequest(BaseModel):
    role: str


class WorkspaceShareSessionRequest(BaseModel):
    session_id: str


# ── Sessions ──────────────────────────────────────────────────────────────────


class SessionCreateRequest(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = "Uncategorized"


class SessionUpdateRequest(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    pinned: Optional[bool] = None
    archived: Optional[bool] = None


class CategoryRequest(BaseModel):
    category: str


class SessionFlagsRequest(BaseModel):
    value: bool


class ImportMessage(BaseModel):
    type: str
    content: str


class ImportRequest(BaseModel):
    session_id: str
    category: str
    messages: List[ImportMessage]


# ── Admin configs / settings ──────────────────────────────────────────────────


class ConfigUpdateRequest(BaseModel):
    configs: Dict[str, str]


class AdminSettingsExportRequest(BaseModel):
    include_secrets: bool = False
    confirm_include_secrets: bool = False


class AdminSettingsImportRequest(BaseModel):
    configs: Dict[str, Any]
    dry_run: bool = True
    conflict_strategy: str = "skip"  # skip|overwrite


class AdminPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class UserProfileUpdateRequest(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    avatar: Optional[str] = None



class AdminUserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "user"
    email: Optional[str] = None
    allowed_categories: Optional[str] = "all"


class AdminUserUpdateRequest(BaseModel):
    role: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    allowed_categories: Optional[str] = None


# ── Admin sessions ────────────────────────────────────────────────────────────


class OrphanAdoptionRunRequest(BaseModel):
    force: bool = False
    batch_size: int = 100


class SessionRepairRequest(BaseModel):
    assign_unowned_to: Optional[str] = None


# ── Notifications ─────────────────────────────────────────────────────────────


class ChatReplyNotificationRequest(BaseModel):
    session_id: str
    reply_preview: str


class NotificationPreferencesUpdateRequest(BaseModel):
    browser_notify_on_away_replies: bool = True
    email_notify_on_away_replies: bool = False
    minimum_notify_interval_seconds: int = 300
    digest_mode: str = "immediate"
    digest_interval_minutes: int = 30


# ── Chat preferences ──────────────────────────────────────────────────────────


class ChatPreferencesUpdateRequest(BaseModel):
    low_token_mode: bool = False
    retrieval_default_preset: str = "balanced"
    retrieval_scope: str = "user"


# ── Tasks ─────────────────────────────────────────────────────────────────────


class TaskCreateRequest(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    due_at: Optional[str] = None
    session_id: Optional[str] = None


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_at: Optional[str] = None
    session_id: Optional[str] = None


class SuggestionTaskCreateRequest(BaseModel):
    session_id: Optional[str] = None


# ── Backup / Restore ──────────────────────────────────────────────────────────


class BackupRestoreRequest(BaseModel):
    backup_json: str
    dry_run: bool = True


class RestorePreflightRequest(BaseModel):
    backup_json: str


class RestoreStartRequest(BaseModel):
    backup_json: str
    preflight_id: str
    confirm_restore: bool = False


class BackupConnectionTestRequest(BaseModel):
    mode: str
    host: Optional[str] = ""
    user: Optional[str] = ""
    password: Optional[str] = ""
    path: Optional[str] = "/"
    share: Optional[str] = ""
    domain: Optional[str] = ""


class BackupFtpTestRequest(BaseModel):
    host: str
    user: str = ""
    password: str = ""
    path: str = "/"
    port: int = 21


class RetentionRunRequest(BaseModel):
    max_age_days: int = 365
    archive_only: bool = True


class RetentionDryRunRequest(BaseModel):
    chat_history_days: int = 365
    recall_index_days: int = 365
    logs_days: int = 30
    backups_days: int = 30


class BackupProfileDestination(BaseModel):
    type: str = "local"
    path: Optional[str] = ""
    host: Optional[str] = ""
    port: Optional[int] = None
    username: Optional[str] = ""
    credential: Optional[str] = ""
    credential_key_ref: Optional[str] = ""


class BackupProfileSchedule(BaseModel):
    cron: Optional[str] = ""
    interval_minutes: Optional[int] = None


class BackupProfileCreateRequest(BaseModel):
    name: str
    enabled: bool = True
    include_database: bool = True
    include_uploads: bool = False
    include_configs: bool = False
    include_logs: bool = False
    destination: BackupProfileDestination
    schedule: BackupProfileSchedule = BackupProfileSchedule()
    retention_count: Optional[int] = None
    retention_days: Optional[int] = None


class BackupProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    include_database: Optional[bool] = None
    include_uploads: Optional[bool] = None
    include_configs: Optional[bool] = None
    include_logs: Optional[bool] = None
    destination: Optional[BackupProfileDestination] = None
    schedule: Optional[BackupProfileSchedule] = None
    retention_count: Optional[int] = None
    retention_days: Optional[int] = None


# ── Full Backup ───────────────────────────────────────────────────────────────


class FullRestoreRequest(BaseModel):
    filename: str
    restore_chats: bool = True
    restore_memories: bool = True
    restore_core_memories: bool = True
    restore_users: bool = True
    restore_configs: bool = True
    restore_personas: bool = True
    restore_tasks: bool = True


# ── Providers ─────────────────────────────────────────────────────────────────


class ProviderTestRequest(BaseModel):
    provider: str


# ── Auth ──────────────────────────────────────────────────────────────────────


class UserLoginResponse(BaseModel):
    username: str
    role: str
    token: str


class UserRegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


class UserLoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False


# ── Network targets ───────────────────────────────────────────────────────────


class TargetModel(BaseModel):
    name: str
    ip_address: str


# ── Notes ─────────────────────────────────────────────────────────────────────


class NoteCreateRequest(BaseModel):
    title: str = "Untitled"
    body: str = ""
    tag: Optional[str] = ""


class NoteUpdateRequest(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    tag: Optional[str] = None


# ── Nudge curation ────────────────────────────────────────────────────────────


class NudgeCurateTriggerRequest(BaseModel):
    session_id: Optional[str] = None
    model_type: str = "ollama"
    dry_run: bool = False
