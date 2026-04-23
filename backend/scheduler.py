import subprocess
import re
import json
import time
from apscheduler.schedulers.background import BackgroundScheduler
from database import (
    get_network_targets,
    list_tasks,
    get_config,
    set_config,
    get_sql_chat_history,
    set_session_category,
)
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from agent import chat_with_agent
from integrations.gmail_api import (
    fetch_todays_messages as fetch_gmail_todays_messages,
    refresh_access_token as refresh_gmail_access_token,
)
from integrations.outlook_graph import (
    fetch_todays_messages as fetch_outlook_todays_messages,
    refresh_access_token as refresh_outlook_access_token,
)

from logging_utils import get_logger

scheduler = BackgroundScheduler()
logger = get_logger(__name__)
LAST_RUN = {"network_sweep": None, "task_reminders": None, "email_digest": None}

def ping_target(ip_address: str) -> dict:
    try:
        # Run ping command with 3 packets, timeout 2s per packet
        result = subprocess.run(
            ['ping', '-c', '3', '-W', '2', ip_address],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        output = result.stdout
        
        if result.returncode == 0:
            # Parse average ping
            # Linux ping format usually: rtt min/avg/max/mdev = 0.525/0.600/0.700/0.050 ms
            # Mac ping format: round-trip min/avg/max/stddev = 0.525/0.600/0.700/0.050 ms
            avg_ping_match = re.search(r'(?:rtt|round-trip) min/avg/max/(?:mdev|stddev) = [0-9.]+?/([0-9.]+)', output)
            avg_ping = avg_ping_match.group(1) if avg_ping_match else "unknown"
            
            # Simple latency check
            try:
                latency = float(avg_ping)
                if latency < 20:
                    status = "Good"
                elif latency < 100:
                    status = "Fair"
                else:
                    status = "Poor"
            except:
                status = "Good"
                
            return {"status": status, "avg_ping": avg_ping, "details": "stable"}
        else:
            return {"status": "Offline", "avg_ping": "N/A", "details": "unreachable"}
    except Exception as e:
        return {"status": "Error", "avg_ping": "N/A", "details": str(e)}

def run_network_sweep():
    LAST_RUN["network_sweep"] = datetime.now(timezone.utc).isoformat()
    LAST_ERRORS["network_sweep"] = None
    logger.info("Running scheduled network sweep")
    targets = get_network_targets()
    if not targets:
        logger.info("No network targets configured")
        return

    report_lines = ["Link Status Overview:"]
    for t in targets:
        ping_result = ping_target(t['ip_address'])
        if ping_result['status'] == 'Offline':
            line = f"{t['name']} Connectivity: Offline (Host unreachable)"
        else:
            line = f"{t['name']} Connectivity: {ping_result['status']} (Average Ping Time: {ping_result['avg_ping']}ms)"
        report_lines.append(line)
    
    final_report = "\n".join(report_lines)
    logger.info("Network sweep complete", extra={"report": final_report, "targets_count": len(targets)})
    
    # Save the report to the "System Reports" chat session in the DB
    session_id = "system_reports"
    try:
        set_session_category(session_id, "System Reports")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ai_message = f"**Automated Network Report ({timestamp})**\n```\n{final_report}\n```"
        history = get_sql_chat_history(session_id)
        history.add_user_message(f"Run daily network sweep for {timestamp}")
        history.add_ai_message(ai_message)
    except Exception as e:
        logger.exception("Error saving network sweep report to DB", exc_info=e)
        LAST_ERRORS["network_sweep"] = str(e)


def run_task_reminders():
    LAST_RUN["task_reminders"] = datetime.now(timezone.utc).isoformat()
    LAST_ERRORS["task_reminders"] = None
    logger.info("Running scheduled task reminders")
    now = datetime.now(timezone.utc)
    soon = now + timedelta(hours=24)
    pending_tasks = list_tasks(due_before=soon.isoformat())
    reminder_lines = []

    for task in pending_tasks:
        status = (task.get("status") or "").lower()
        if status in {"done", "completed", "cancelled"}:
            continue
        due_at = task.get("due_at")
        if not due_at:
            continue
        due_dt = due_at if isinstance(due_at, datetime) else None
        if not due_dt:
            continue
        if due_dt.tzinfo is None:
            due_dt = due_dt.replace(tzinfo=timezone.utc)

        if due_dt < now:
            reminder_lines.append(f"⚠️ Overdue: #{task['id']} {task['title']} (due {due_dt.isoformat()})")
        else:
            reminder_lines.append(f"⏰ Due soon: #{task['id']} {task['title']} (due {due_dt.isoformat()})")

    if not reminder_lines:
        logger.info("No task reminders needed")
        return

    session_id = "system_tasks"
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    summary = "\n".join(reminder_lines)
    try:
        set_session_category(session_id, "System Tasks")
        history = get_sql_chat_history(session_id)
        history.add_user_message(f"Run task reminder check at {timestamp}")
        history.add_ai_message(f"**Task Reminder Report ({timestamp})**\n{summary}")
        logger.info("Task reminders recorded", extra={"reminder_count": len(reminder_lines)})
    except Exception as e:
        logger.exception("Error saving task reminders", exc_info=e)
        LAST_ERRORS["task_reminders"] = str(e)


def _load_email_credentials(provider: str):
    raw = get_config(f"integration_email_{provider}_credentials", "{}")
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _store_email_credentials(provider: str, credentials: dict):
    set_config(f"integration_email_{provider}_credentials", json.dumps(credentials))


def _ensure_access_token(provider: str) -> str:
    creds = _load_email_credentials(provider)
    expires_at = int(creds.get("expires_at") or 0)
    if creds.get("access_token") and expires_at > int(time.time()) + 60:
        return creds["access_token"]

    if provider == "gmail":
        creds = refresh_gmail_access_token(creds)
    else:
        creds = refresh_outlook_access_token(creds)
    _store_email_credentials(provider, creds)
    return creds["access_token"]


def run_email_digest_job():
    LAST_RUN["email_digest"] = datetime.now(timezone.utc).isoformat()
    provider = (get_config("email_digest_provider", "outlook") or "outlook").strip().lower()
    tz_name = (get_config("email_digest_timezone", "UTC") or "UTC").strip()
    max_results = int(get_config("email_digest_max_results", "25") or "25")
    session_id = "system_email_reports"

    try:
        ZoneInfo(tz_name)
    except Exception:
        tz_name = "UTC"

    try:
        token = _ensure_access_token(provider)
        if provider == "gmail":
            messages = fetch_gmail_todays_messages(token, tz=tz_name, max_results=max_results)
        else:
            messages = fetch_outlook_todays_messages(token, tz=tz_name, max_results=max_results)
    except Exception as exc:
        logger.exception("Email digest job failed before summarization", exc_info=exc, extra={"provider": provider})
        LAST_ERRORS["email_digest"] = str(exc)
        return

    if not messages:
        logger.info("Email digest job: no messages found for today", extra={"provider": provider})
        return

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
        f"Generate a daily inbox digest for {provider.title()} on {date_label} ({tz_name}). "
        "Include key themes, urgent items, time-sensitive items, and suggested next actions.\n\n"
        "Messages:\n"
        + "\n\n".join(digest_lines)
    )
    model_type = get_config("default_model", "ollama") or "ollama"
    chat_with_agent(
        session_id=session_id,
        message=prompt,
        model_type=model_type,
        api_key=None,
        memory_mode="full",
        use_web_search=False,
        attachments=[],
    )
    logger.info("Email digest job saved", extra={"session_id": session_id, "provider": provider})

def start_scheduler():
    if not scheduler.running:
        # Run every day at 9:00 AM
        scheduler.add_job(run_network_sweep, 'cron', hour=9, minute=0)
        # Run task reminder checks every 10 minutes
        scheduler.add_job(run_task_reminders, 'interval', minutes=10)
        try:
            digest_hour = int(get_config("email_digest_hour", "7") or "7")
        except ValueError:
            digest_hour = 7
        try:
            digest_minute = int(get_config("email_digest_minute", "30") or "30")
        except ValueError:
            digest_minute = 30
        digest_timezone = get_config("email_digest_timezone", "UTC") or "UTC"
        scheduler.add_job(
            run_email_digest_job,
            "cron",
            hour=digest_hour,
            minute=digest_minute,
            timezone=digest_timezone,
        )
        scheduler.start()
        logger.info("Background scheduler started")


def get_scheduler_diagnostics() -> dict:
    return {
        "running": scheduler.running,
        "last_run": LAST_RUN,
        "last_errors": LAST_ERRORS,
        "jobs": [job.id for job in scheduler.get_jobs()],
    }
