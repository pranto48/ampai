"""Integrations router: Telegram webhooks/admin, email summary, context pull."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from email.header import decode_header
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from agent import chat_with_agent
from core.deps import UserContext, require_admin_user, require_authenticated_user
from core.helpers import (
    _config_bool,
    _create_memory_candidate,
    _get_memory_policy,
    _load_integration_credentials,
    _save_integration_credentials,
)
from core.models import (
    EmailSummaryRequest,
    EmailSummaryTodayRequest,
    TelegramIntegrationSaveRequest,
)
from database import (
    create_user as db_create_user,
)
from database import (
    ensure_session_owner,
    get_all_sessions,
    get_config,
    get_or_create_telegram_user,
    get_user,
    log_audit_event,
    lookup_username_by_telegram_user_id,
    set_config,
    touch_session,
    touch_session_updated_at,
)
from database import (
    update_user as db_update_user,
)
from fastapi import APIRouter, Depends, Header, HTTPException
from integrations.gmail_api import (
    fetch_todays_messages as fetch_gmail_todays_messages,
)
from integrations.gmail_api import (
    refresh_access_token as refresh_gmail_access_token,
)
from integrations.telegram_api import (
    TelegramBotConfig,
    TelegramBotService,
    delete_webhook,
    get_me,
    send_message,
    set_webhook,
)

from passlib.context import CryptContext

router = APIRouter(tags=["integrations"])
logger = logging.getLogger("ampai")

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# ── Telegram constants ────────────────────────────────────────────────────────
TELEGRAM_MAX_MESSAGE_CHARS = 4000
TELEGRAM_RATE_LIMIT_COUNT = 8
TELEGRAM_RATE_LIMIT_WINDOW_SECONDS = 20
TELEGRAM_GENERIC_FAILURE_TEXT = (
    "Sorry, something went wrong while processing your message."
)
TELEGRAM_POLL_TIMEOUT_SECONDS = 25
TELEGRAM_POLL_SLEEP_SECONDS = 1.5

_telegram_rate_limit_lock = threading.Lock()
_telegram_rate_limit_buckets: Dict[str, List[float]] = {}
_telegram_poller_started = False
_telegram_poller_lock = threading.Lock()
_telegram_offset_lock = threading.Lock()
_telegram_next_update_offset = 0
_telegram_processed_update_ids: set = set()


def _mask_telegram_token(token: str) -> str:
    normalized = (token or "").strip()
    if not normalized:
        return ""
    if len(normalized) <= 8:
        return "****"
    return f"{normalized[:4]}...{normalized[-4:]}"


def _extract_telegram_update_fields(update: Dict[str, Any]) -> Dict[str, Any]:
    message_obj = update.get("message") or update.get("edited_message") or {}
    from_obj = message_obj.get("from") or {}
    chat_obj = message_obj.get("chat") or {}
    text = (message_obj.get("text") or "").strip()
    return {
        "user_id": from_obj.get("id"),
        "chat_id": chat_obj.get("id"),
        "text": text,
        "is_text_update": bool(text),
    }


def _sanitize_telegram_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text).strip()
    if len(text) > TELEGRAM_MAX_MESSAGE_CHARS:
        text = text[:TELEGRAM_MAX_MESSAGE_CHARS]
    return text


def _resolve_telegram_username(user_id: Any) -> str:
    user_id_str = str(user_id or "").strip()
    if not user_id_str:
        return "telegram-bot"
    strategy = (
        (get_config("telegram_user_mapping_mode", "per_user") or "per_user")
        .strip()
        .lower()
    )
    if strategy == "service_account":
        return "telegram-bot"
    return f"telegram-{user_id_str}"


def _send_telegram_message(bot_token: str, chat_id: Any, text: str) -> None:
    if not bot_token or not chat_id or not text:
        return
    text = str(text)[:3500]
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception:
        logger.exception(
            "telegram sendMessage failed: chat_id=%s token=%s",
            chat_id,
            _mask_telegram_token(bot_token),
        )
        raise


def _is_rate_limited(user_id: Any, chat_id: Any) -> bool:
    now = time.time()
    key = f"{user_id}:{chat_id}"
    with _telegram_rate_limit_lock:
        bucket = _telegram_rate_limit_buckets.get(key, [])
        bucket = [ts for ts in bucket if now - ts < TELEGRAM_RATE_LIMIT_WINDOW_SECONDS]
        if len(bucket) >= TELEGRAM_RATE_LIMIT_COUNT:
            _telegram_rate_limit_buckets[key] = bucket
            return True
        bucket.append(now)
        _telegram_rate_limit_buckets[key] = bucket
    return False


def _process_telegram_update(update: Dict[str, Any]) -> None:
    fields = _extract_telegram_update_fields(update)
    user_id = fields.get("user_id")
    chat_id = fields.get("chat_id")
    incoming_text = _sanitize_telegram_text(fields.get("text"))
    if (
        not fields.get("is_text_update")
        or not user_id
        or not chat_id
        or not incoming_text
    ):
        return
    if _is_rate_limited(user_id, chat_id):
        return
    session_id = f"tg_{chat_id}_{user_id}"
    resolved_username = _resolve_telegram_username(user_id)
    mapped_username = lookup_username_by_telegram_user_id(user_id)
    username = (
        mapped_username
        or get_or_create_telegram_user(
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            default_username=resolved_username,
        )
        or resolved_username
    )
    if not get_user(username):
        db_create_user(
            username=username,
            role="user",
            password_hash=pwd_context.hash(uuid.uuid4().hex),
        )
    ensure_session_owner(session_id, username)
    touch_session(session_id)
    model_type = (get_config("default_model", "ollama") or "ollama").strip().lower()
    policy = _get_memory_policy(username)
    try:
        result = chat_with_agent(
            session_id=session_id,
            message=incoming_text,
            model_type=model_type,
            api_key=None,
            model_name=None,
            memory_mode="indexed",
            memory_top_k=5,
            recency_bias=0.6,
            category_filter="",
            use_web_search=False,
            attachments=[],
            chat_output_mode="normal",
            username=username,
            is_admin=False,
            allowed_memory_categories=policy.get("allowed_categories") or [],
            persist_memory=bool(policy.get("auto_capture_enabled", True)),
            require_memory_approval=bool(policy.get("require_approval", False)),
            pii_strict_mode=bool(policy.get("pii_strict_mode", True)),
        )
        response_text = str((result or {}).get("response") or "").strip()
        if response_text:
            try:
                _send_telegram_message(
                    (get_config("telegram_bot_token") or "").strip(),
                    chat_id,
                    response_text,
                )
            except Exception:
                logger.exception("telegram provider send failure")
                log_audit_event(
                    username=username,
                    action="integration.telegram.provider_send_failure",
                    session_id=session_id,
                )
                raise
        touch_session_updated_at(session_id)
        log_audit_event(
            username=username,
            action="integration.telegram.message_processed",
            session_id=session_id,
        )
    except Exception:
        logger.exception("telegram update processing failed")
        try:
            _send_telegram_message(
                (get_config("telegram_bot_token") or "").strip(),
                chat_id,
                TELEGRAM_GENERIC_FAILURE_TEXT,
            )
        except Exception:
            logger.exception("telegram provider send failure")
            log_audit_event(
                username=username,
                action="integration.telegram.provider_send_failure",
                session_id=session_id,
            )


def _mark_telegram_update_processed(update_id: Any) -> bool:
    global _telegram_next_update_offset
    try:
        normalized = int(update_id)
    except (TypeError, ValueError):
        return True
    with _telegram_offset_lock:
        if normalized in _telegram_processed_update_ids:
            return False
        _telegram_processed_update_ids.add(normalized)
        if len(_telegram_processed_update_ids) > 2000:
            floor = max(_telegram_next_update_offset - 2000, 0)
            _telegram_processed_update_ids.difference_update(
                {uid for uid in _telegram_processed_update_ids if uid < floor}
            )
    return True


def _poll_telegram_updates_forever() -> None:
    global _telegram_next_update_offset
    logger.info("Starting Telegram polling worker")
    while True:
        try:
            if not _config_bool("telegram_enabled", default=False) or not _config_bool(
                "telegram_polling_enabled", default=False
            ):
                time.sleep(3)
                continue
            bot_token = (get_config("telegram_bot_token") or "").strip()
            if not bot_token:
                time.sleep(5)
                continue
            with _telegram_offset_lock:
                offset = max(0, int(_telegram_next_update_offset or 0))
            params = urllib.parse.urlencode(
                {
                    "timeout": TELEGRAM_POLL_TIMEOUT_SECONDS,
                    "offset": offset,
                    "allowed_updates": json.dumps(
                        ["message", "edited_message", "callback_query"]
                    ),
                }
            )
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates?{params}"
            with urllib.request.urlopen(
                url, timeout=TELEGRAM_POLL_TIMEOUT_SECONDS + 10
            ) as resp:
                payload = json.loads((resp.read() or b"{}").decode("utf-8"))
            if not isinstance(payload, dict) or not payload.get("ok"):
                time.sleep(TELEGRAM_POLL_SLEEP_SECONDS)
                continue
            for update in payload.get("result") or []:
                update_id = update.get("update_id")
                if not _mark_telegram_update_processed(update_id):
                    continue
                if isinstance(update_id, int):
                    with _telegram_offset_lock:
                        _telegram_next_update_offset = max(
                            _telegram_next_update_offset, update_id + 1
                        )
                _process_telegram_update(update or {})
        except Exception:
            logger.exception("telegram polling worker iteration failed")
            time.sleep(TELEGRAM_POLL_SLEEP_SECONDS)


def _start_telegram_poller_if_enabled() -> None:
    global _telegram_poller_started
    if not _config_bool("telegram_polling_enabled", default=False):
        return
    with _telegram_poller_lock:
        if _telegram_poller_started:
            return
        worker = threading.Thread(
            target=_poll_telegram_updates_forever,
            daemon=True,
            name="ampai-telegram-poller",
        )
        worker.start()
        _telegram_poller_started = True


# ── Telegram admin endpoints ──────────────────────────────────────────────────


@router.get("/api/admin/integrations/telegram/status")
def admin_telegram_status(current_user: UserContext = Depends(require_admin_user)):
    bot_token = (get_config("telegram_bot_token") or "").strip()
    webhook_url = (get_config("telegram_webhook_url") or "").strip()
    enabled = _config_bool("telegram_enabled", default=False)
    polling_enabled = _config_bool("telegram_polling_enabled", default=False)
    log_audit_event(
        username=current_user.username, action="integration.telegram.admin_status"
    )
    return {
        "ok": True,
        "enabled": enabled,
        "polling_enabled": polling_enabled,
        "webhook_url": webhook_url,
        "token_configured": bool(bot_token),
        "token_masked": _mask_telegram_token(bot_token),
        "secret_configured": bool(
            (get_config("telegram_webhook_secret") or "").strip()
        ),
    }


@router.post("/api/admin/integrations/telegram/save")
def admin_telegram_save(
    request: TelegramIntegrationSaveRequest,
    current_user: UserContext = Depends(require_admin_user),
):
    set_config("telegram_bot_token", request.bot_token or "")
    set_config("telegram_webhook_url", (request.webhook_url or "").strip())
    set_config("telegram_webhook_secret", (request.secret_token or "").strip())
    set_config("telegram_enabled", "true" if request.enabled else "false")
    log_audit_event(
        username=current_user.username, action="integration.telegram.admin_save"
    )
    return {
        "ok": True,
        "enabled": bool(request.enabled),
        "polling_enabled": _config_bool("telegram_polling_enabled", default=False),
        "webhook_url": (request.webhook_url or "").strip(),
        "token_configured": bool((request.bot_token or "").strip()),
        "token_masked": _mask_telegram_token(request.bot_token or ""),
    }


@router.post("/api/admin/integrations/telegram/enable-polling")
def admin_telegram_enable_polling(
    current_user: UserContext = Depends(require_admin_user),
):
    token = (get_config("telegram_bot_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Telegram bot token is required")
    try:
        delete_webhook(token)
    except Exception:
        pass
    set_config("telegram_polling_enabled", "true")
    set_config("telegram_enabled", "true")
    _start_telegram_poller_if_enabled()
    log_audit_event(
        username=current_user.username, action="integration.telegram.enable_polling"
    )
    return {"ok": True, "mode": "polling"}


@router.post("/api/admin/integrations/telegram/disable-polling")
def admin_telegram_disable_polling(
    current_user: UserContext = Depends(require_admin_user),
):
    set_config("telegram_polling_enabled", "false")
    log_audit_event(
        username=current_user.username, action="integration.telegram.disable_polling"
    )
    return {"ok": True, "mode": "webhook"}


@router.get("/api/admin/integrations/telegram/webhook-info")
def admin_telegram_webhook_info(
    current_user: UserContext = Depends(require_admin_user),
):
    token = (get_config("telegram_bot_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Telegram bot token not configured")
    try:
        url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
        with urllib.request.urlopen(url, timeout=10) as resp:
            payload = json.loads((resp.read() or b"{}").decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Telegram API error: {exc}"
        ) from exc
    result = payload.get("result") or {}
    return {
        "ok": True,
        "url": result.get("url", ""),
        "pending_update_count": result.get("pending_update_count", 0),
        "last_error_date": result.get("last_error_date"),
        "last_error_message": result.get("last_error_message", ""),
        "max_connections": result.get("max_connections"),
        "has_custom_certificate": result.get("has_custom_certificate", False),
        "allowed_updates": result.get("allowed_updates", []),
    }


@router.get("/api/admin/integrations/telegram/sessions")
def admin_telegram_sessions(current_user: UserContext = Depends(require_admin_user)):
    all_sessions = get_all_sessions()
    tg_sessions = [
        s for s in (all_sessions or []) if (s.get("session_id") or "").startswith("tg_")
    ]
    return {"sessions": tg_sessions, "total": len(tg_sessions)}


@router.post("/api/admin/integrations/telegram/test")
def admin_telegram_test(current_user: UserContext = Depends(require_admin_user)):
    token = (get_config("telegram_bot_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Telegram bot token is required")
    try:
        payload = get_me(token)
    except urllib.error.HTTPError as exc:
        detail = (exc.read() or b"").decode("utf-8", errors="ignore")[:500]
        raise HTTPException(
            status_code=502, detail=f"Telegram getMe failed: {detail or exc.reason}"
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Telegram getMe failed") from exc
    if not payload.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=str(payload.get("description") or "Telegram getMe failed"),
        )
    result = payload.get("result") or {}
    log_audit_event(
        username=current_user.username, action="integration.telegram.admin_test"
    )
    return {
        "ok": True,
        "bot_username": result.get("username"),
        "bot_id": result.get("id"),
    }


@router.post("/api/admin/integrations/telegram/connect")
def admin_telegram_connect(current_user: UserContext = Depends(require_admin_user)):
    token = (get_config("telegram_bot_token") or "").strip()
    webhook_url = (get_config("telegram_webhook_url") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Telegram bot token is required")
    if not webhook_url:
        raise HTTPException(
            status_code=400, detail="Telegram webhook URL is not configured"
        )
    secret_token = (get_config("telegram_webhook_secret") or "").strip()
    try:
        payload = set_webhook(token, webhook_url, secret_token=secret_token or None)
    except urllib.error.HTTPError as exc:
        detail = (exc.read() or b"").decode("utf-8", errors="ignore")[:500]
        raise HTTPException(
            status_code=502,
            detail=f"Telegram setWebhook failed: {detail or exc.reason}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Telegram setWebhook failed"
        ) from exc
    if not payload.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=str(payload.get("description") or "Telegram setWebhook failed"),
        )
    log_audit_event(
        username=current_user.username, action="integration.telegram.admin_connect"
    )
    return {"ok": True, "description": payload.get("description", "Webhook connected")}


@router.post("/api/admin/integrations/telegram/disconnect")
def admin_telegram_disconnect(current_user: UserContext = Depends(require_admin_user)):
    token = (get_config("telegram_bot_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Telegram bot token is required")
    try:
        payload = delete_webhook(token)
    except urllib.error.HTTPError as exc:
        detail = (exc.read() or b"").decode("utf-8", errors="ignore")[:500]
        raise HTTPException(
            status_code=502,
            detail=f"Telegram deleteWebhook failed: {detail or exc.reason}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Telegram deleteWebhook failed"
        ) from exc
    if not payload.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=str(payload.get("description") or "Telegram deleteWebhook failed"),
        )
    log_audit_event(
        username=current_user.username, action="integration.telegram.admin_disconnect"
    )
    return {
        "ok": True,
        "description": payload.get("description", "Webhook disconnected"),
    }


@router.post("/api/integrations/telegram/webhook")
def telegram_webhook(
    payload: Dict[str, Any],
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
):
    if not _config_bool("telegram_enabled", default=False):
        return {"status": "ignored", "reason": "disabled"}
    bot_token = (get_config("telegram_bot_token") or "").strip()
    if not bot_token:
        raise HTTPException(status_code=400, detail="Telegram bot token is required")
    expected_secret = (get_config("telegram_webhook_secret") or "").strip()
    if (
        expected_secret
        and (x_telegram_bot_api_secret_token or "").strip() != expected_secret
    ):
        logger.warning("telegram webhook rejected: invalid secret")
        return {"status": "ok"}
    fields = _extract_telegram_update_fields(payload or {})
    chat_id = fields.get("chat_id")
    incoming_text = _sanitize_telegram_text(fields.get("text"))
    if not fields.get("is_text_update") or not chat_id or not incoming_text:
        return {"status": "ok"}
    session_id = f"tg_{chat_id}"
    username = "telegram-bot"
    model_type = (get_config("default_model", "ollama") or "ollama").strip().lower()
    try:
        result = chat_with_agent(
            session_id=session_id,
            message=incoming_text,
            model_type=model_type,
            api_key=None,
            model_name=None,
            memory_mode="indexed",
            memory_top_k=5,
            recency_bias=0.6,
            category_filter="",
            use_web_search=False,
            attachments=[],
            chat_output_mode="normal",
            username=username,
            is_admin=False,
            allowed_memory_categories=[],
            persist_memory=True,
            require_memory_approval=False,
            pii_strict_mode=True,
        )
        response_text = str((result or {}).get("response") or "").strip()
        if response_text:
            send_message(bot_token, chat_id, response_text)
        ensure_session_owner(session_id, username)
        touch_session(session_id)
        log_audit_event(
            username=username,
            action="integration.telegram.webhook_processed",
            session_id=session_id,
        )
    except Exception:
        logger.exception("telegram webhook processing failed")
        log_audit_event(
            username=username,
            action="integration.telegram.webhook.process_failure",
            session_id=session_id,
        )
    return {"status": "ok"}


# ── TelegramBotService-based endpoints (design spec paths) ────────────────────
# These endpoints use the TelegramBotService class for full lifecycle management
# and expose the canonical paths from the design document.


def _get_telegram_bot_service() -> TelegramBotService:
    """
    Build a TelegramBotService instance from current app_configs.
    This is constructed per-request to always reflect the latest config.
    """
    bot_token = (get_config("telegram_bot_token") or "").strip()
    webhook_url = (get_config("telegram_webhook_url") or "").strip()
    webhook_secret = (get_config("telegram_webhook_secret") or "").strip()
    enabled = _config_bool("telegram_enabled", default=False)
    polling_enabled = _config_bool("telegram_polling_enabled", default=False)

    # Parse allowed user IDs from config (comma-separated list)
    allowed_ids_raw = (get_config("allowed_telegram_user_ids") or "").strip()
    allowed_ids: List[int] = []
    if allowed_ids_raw:
        for part in allowed_ids_raw.split(","):
            part = part.strip()
            if part.isdigit():
                allowed_ids.append(int(part))

    tool_access = _config_bool("telegram_tool_access_enabled", default=False)

    config = TelegramBotConfig(
        bot_token=bot_token,
        webhook_url=webhook_url,
        webhook_secret=webhook_secret,
        enabled=enabled,
        polling_enabled=polling_enabled,
        allowed_telegram_user_ids=allowed_ids,
        telegram_tool_access_enabled=tool_access,
    )

    def _chat_handler(session_id, message, username, **kwargs):
        model_type = kwargs.get("model_type") or (
            get_config("default_model", "ollama") or "ollama"
        ).strip().lower()
        policy = _get_memory_policy(username)
        return chat_with_agent(
            session_id=session_id,
            message=message,
            model_type=model_type,
            api_key=None,
            model_name=None,
            memory_mode=kwargs.get("memory_mode", "indexed"),
            memory_top_k=kwargs.get("memory_top_k", 5),
            recency_bias=kwargs.get("recency_bias", 0.6),
            category_filter="",
            use_web_search=kwargs.get("use_web_search", False),
            attachments=[],
            chat_output_mode="normal",
            username=username,
            is_admin=False,
            allowed_memory_categories=policy.get("allowed_categories") or [],
            persist_memory=bool(policy.get("auto_capture_enabled", True)),
            require_memory_approval=bool(policy.get("require_approval", False)),
            pii_strict_mode=bool(policy.get("pii_strict_mode", True)),
        )

    def _audit_logger(username, action, session_id=None, details=None):
        log_audit_event(
            username=username,
            action=action,
            session_id=session_id,
        )

    def _user_resolver(telegram_user_id):
        return lookup_username_by_telegram_user_id(telegram_user_id)

    def _session_mgr(session_id, username):
        ensure_session_owner(session_id, username)
        touch_session(session_id)

    return TelegramBotService(
        config=config,
        chat_handler=_chat_handler,
        audit_logger=_audit_logger,
        user_resolver=_user_resolver,
        session_manager=_session_mgr,
    )


@router.post("/api/telegram/webhook")
def telegram_webhook_v2(
    payload: Dict[str, Any],
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
):
    """
    Telegram webhook receiver (design spec path).
    Uses TelegramBotService for full lifecycle processing including
    user resolution, rate limiting, access control, and audit logging.
    """
    if not _config_bool("telegram_enabled", default=False):
        return {"status": "ignored", "reason": "disabled"}

    bot_token = (get_config("telegram_bot_token") or "").strip()
    if not bot_token:
        raise HTTPException(status_code=400, detail="Telegram bot token is required")

    # Validate webhook secret if configured
    expected_secret = (get_config("telegram_webhook_secret") or "").strip()
    if (
        expected_secret
        and (x_telegram_bot_api_secret_token or "").strip() != expected_secret
    ):
        logger.warning("telegram webhook rejected: invalid secret")
        return {"status": "ok"}

    service = _get_telegram_bot_service()
    return service.process_webhook_update(payload or {})


@router.post("/api/admin/telegram/enable-polling")
def admin_telegram_enable_polling_v2(
    current_user: UserContext = Depends(require_admin_user),
):
    """
    Start long-polling mode (design spec path).
    Uses TelegramBotService which deregisters any active webhook first.
    """
    token = (get_config("telegram_bot_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Telegram bot token is required")

    # Deregister webhook (only one mode active at a time)
    try:
        delete_webhook(token)
    except Exception:
        pass

    set_config("telegram_polling_enabled", "true")
    set_config("telegram_enabled", "true")
    _start_telegram_poller_if_enabled()

    log_audit_event(
        username=current_user.username, action="integration.telegram.enable_polling"
    )
    return {"ok": True, "mode": "polling"}


@router.post("/api/admin/telegram/disable-polling")
def admin_telegram_disable_polling_v2(
    current_user: UserContext = Depends(require_admin_user),
):
    """
    Stop long-polling mode (design spec path).
    """
    set_config("telegram_polling_enabled", "false")

    log_audit_event(
        username=current_user.username, action="integration.telegram.disable_polling"
    )
    return {"ok": True, "mode": "webhook"}


# ── Email integration ─────────────────────────────────────────────────────────


def _ensure_valid_email_access_token(provider: str) -> str:
    credentials = _load_integration_credentials(provider)
    if not credentials:
        raise HTTPException(
            status_code=400, detail=f"{provider} integration is not configured"
        )
    expires_at = int(credentials.get("expires_at") or 0)
    if credentials.get("access_token") and expires_at > int(time.time()) + 60:
        return credentials["access_token"]
    if provider == "gmail":
        refreshed = refresh_gmail_access_token(credentials)
    elif provider == "outlook":
        from integrations.outlook_api import refresh_access_token as refresh_outlook

        refreshed = refresh_outlook(credentials)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")
    _save_integration_credentials(provider, refreshed)
    return refreshed["access_token"]


def _fetch_todays_email_messages(
    provider: str, timezone_name: str, max_results: int
) -> List[Dict[str, str]]:
    access_token = _ensure_valid_email_access_token(provider)
    if provider == "gmail":
        return fetch_gmail_todays_messages(
            access_token=access_token, tz=timezone_name, max_results=max_results
        )
    if provider == "outlook":
        from integrations.outlook_api import fetch_todays_messages as fetch_outlook

        return fetch_outlook(
            access_token=access_token, tz=timezone_name, max_results=max_results
        )
    raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")


@router.post("/api/integrations/email/summary-today")
def summarize_todays_email(
    request: EmailSummaryTodayRequest,
    _: UserContext = Depends(require_authenticated_user),
):
    provider = request.provider.strip().lower()
    tz_name = request.timezone.strip() or "UTC"
    try:
        ZoneInfo(tz_name)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid timezone: {tz_name}"
        ) from exc
    messages = _fetch_todays_email_messages(
        provider=provider,
        timezone_name=tz_name,
        max_results=max(1, min(request.max_results, 100)),
    )
    if not messages:
        return {
            "status": "success",
            "summary": "No messages found for today.",
            "messages_count": 0,
        }
    digest_lines = []
    for idx, msg in enumerate(messages, 1):
        digest_lines.append(
            f"{idx}. From: {msg.get('from', '')}\n"
            f"   Subject: {msg.get('subject', '(No subject)')}\n"
            f"   Date: {msg.get('date', '')}\n"
            f"   Snippet: {msg.get('snippet', '')}"
        )
    date_label = datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d")
    prompt = (
        f"Summarize my {provider.title()} email inbox for {date_label} ({tz_name}). "
        "Provide: (1) key topics, (2) urgent follow-ups, (3) calendar/time-sensitive items, "
        "(4) a concise executive digest.\n\n"
        "Today's messages:\n" + "\n\n".join(digest_lines)
    )
    model_type = request.model_type or get_config("default_model", "ollama")
    result = chat_with_agent(
        session_id="system_email_summary",
        message=prompt,
        model_type=model_type,
        api_key=request.api_key,
        memory_mode="full",
        use_web_search=False,
        attachments=[],
    )
    return {
        "status": "success",
        "provider": provider,
        "timezone": tz_name,
        "messages_count": len(messages),
        "summary": result.get("content", ""),
        "session_id": "system_email_summary",
    }


@router.post("/api/email/summary/today")
def summarize_today_email_imap(
    request: EmailSummaryRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    import email as _email
    import imaplib

    from database import get_all_configs

    configs = get_all_configs()
    host = configs.get("imap_host")
    imap_username = configs.get("imap_username")
    password = configs.get("imap_password")
    if not host or not imap_username or not password:
        raise HTTPException(
            status_code=400,
            detail="Set imap_host, imap_username, imap_password in admin configs",
        )
    today = datetime.now().strftime("%d-%b-%Y")
    items = []
    try:
        with imaplib.IMAP4_SSL(host) as mail:
            mail.login(imap_username, password)
            mail.select("INBOX")
            status, data = mail.search(None, f'(SINCE "{today}")')
            if status != "OK":
                raise HTTPException(status_code=500, detail="Failed to query mailbox")
            for num in data[0].split()[-50:]:
                _, msg_data = mail.fetch(num, "(RFC822)")
                msg = _email.message_from_bytes(msg_data[0][1])
                frm = msg.get("From", "Unknown")
                subject = _decode_subject(msg.get("Subject", ""))
                date = msg.get("Date", "")
                items.append(f"From: {frm}\nSubject: {subject}\nDate: {date}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email fetch error: {e}")
    if not items:
        return {"summary": "No emails found for today.", "email_count": 0}
    prompt = (
        "Summarize today's emails into: key updates, urgent actions, follow-ups, and decisions.\n\n"
        + "\n\n---\n\n".join(items)
    )
    result = chat_with_agent(
        session_id=request.session_id,
        message=prompt,
        model_type=request.model_type,
        api_key=request.api_key,
        memory_mode="indexed",
        use_web_search=False,
        attachments=[],
    )
    return {
        "summary": result.get("response") if isinstance(result, dict) else result,
        "email_count": len(items),
    }


def _decode_subject(raw_subject: Any) -> str:
    if not raw_subject:
        return "(No Subject)"
    parts = decode_header(raw_subject)
    out = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(enc or "utf-8", errors="ignore"))
        else:
            out.append(chunk)
    return "".join(out)


# ── Context pull ──────────────────────────────────────────────────────────────


@router.post("/api/integrations/context/pull")
def pull_external_context(
    payload: Dict[str, Any],
    current_user: UserContext = Depends(require_authenticated_user),
):
    provider = (payload.get("provider") or "email").strip().lower()
    if provider not in {"email", "calendar"}:
        raise HTTPException(
            status_code=400, detail="provider must be email or calendar"
        )
    summary = ""
    if provider == "email":
        timezone_name = (payload.get("timezone") or "UTC").strip() or "UTC"
        messages = _fetch_todays_email_messages(
            provider="outlook", timezone_name=timezone_name, max_results=20
        )
        summary = "\n".join(
            [
                f"- {(m.get('subject') or '(no subject)')} | {(m.get('from') or '')}"
                for m in messages[:15]
            ]
        )
    else:
        calendar_feed = (get_config("calendar_feed_url") or "").strip()
        summary = f"Calendar connector configured: {'yes' if calendar_feed else 'no'}; events sync placeholder."
    session_id = (payload.get("session_id") or "external_context").strip()
    created = _create_memory_candidate(
        current_user.username,
        session_id,
        f"[{provider.upper()} CONTEXT]\n{summary}",
        confidence=0.7,
    )
    return {"status": "success", "provider": provider, "candidate": created}
