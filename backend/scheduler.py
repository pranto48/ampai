import subprocess
import re
import shutil
import json
import time
import urllib.request
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from database import (
    get_network_targets,
    list_tasks,
    get_config,
    set_config,
    get_sql_chat_history,
    set_session_category,
    auto_complete_due_tasks,
    list_pending_reply_notifications_for_digest,
    mark_pending_reply_notifications_delivered,
    summarize_approved_memories,
    create_curator_nudge,
    list_agent_skills,
    get_skill_performance,
    set_config,
    get_config,
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
logger = logging.getLogger("ampai.scheduler")



def _send_resend_email(subject: str, body_text: str):
    api_key = (get_config("resend_api_key") or "").strip()
    from_email = (get_config("resend_from_email") or "").strip()
    to_email = (get_config("notification_email_to") or "").strip()
    if not api_key or not from_email or not to_email:
        return False
    payload = json.dumps(
        {"from": from_email, "to": [to_email], "subject": subject, "text": body_text}
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            return True
    except Exception:
        return False


def _send_resend_email(subject: str, body_text: str):
    api_key = (get_config("resend_api_key") or "").strip()
    from_email = (get_config("resend_from_email") or "").strip()
    to_email = (get_config("notification_email_to") or "").strip()
    if not api_key or not from_email or not to_email:
        return False
    payload = json.dumps(
        {"from": from_email, "to": [to_email], "subject": subject, "text": body_text}
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            return True
    except Exception:
        return False

def ping_target(ip_address: str) -> dict:
    ping_binary = shutil.which('ping')
    if not ping_binary:
        return {
            "status": "Error",
            "avg_ping": "N/A",
            "details": "Ping utility is not installed in this runtime",
        }

    try:
        result = subprocess.run(
            [ping_binary, '-c', '3', '-W', '2', ip_address],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        output = result.stdout
        if result.returncode == 0:
            avg_ping_match = re.search(r'(?:rtt|round-trip) min/avg/max/(?:mdev|stddev) = [0-9.]+?/([0-9.]+)', output)
            avg_ping = avg_ping_match.group(1) if avg_ping_match else "unknown"
            try:
                latency = float(avg_ping)
                status = "Good" if latency < 20 else "Fair" if latency < 100 else "Poor"
            except Exception:
                status = "Good"
            return {"status": status, "avg_ping": avg_ping, "details": "stable"}
        return {"status": "Offline", "avg_ping": "N/A", "details": "unreachable"}
    except Exception as e:
        return {"status": "Error", "avg_ping": "N/A", "details": str(e)}


def run_network_sweep():
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
    logger.info("Network Sweep Complete: %s", final_report)

    session_id = "system_reports"
    try:
        with engine.connect() as conn:
            upsert_meta = text(
                "INSERT INTO session_metadata (session_id, category, pinned, archived, updated_at) VALUES (:s, :c, FALSE, FALSE, :u) "
                "ON CONFLICT (session_id) DO UPDATE SET category = EXCLUDED.category, updated_at = EXCLUDED.updated_at"
            )
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(upsert_meta, {"s": session_id, "c": "System Reports", "u": now})

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ai_message = f"**Automated Network Report ({timestamp})**\n```\n{final_report}\n```"
            conn.execute(text("INSERT INTO message_store (session_id, message) VALUES (:s, :m)"), {"s": session_id, "m": f"Run daily network sweep for {timestamp}"})
            conn.execute(text("INSERT INTO message_store (session_id, message) VALUES (:s, :m)"), {"s": session_id, "m": ai_message})
            conn.commit()
    except Exception as e:
        logger.exception("Error saving report to DB: %s", e)


def run_task_digest():
    tasks = list_tasks(status='todo')
    overdue = []
    reminder_lines = []
    now = datetime.now(timezone.utc)
    for t in tasks:
        due_at = t.get('due_at')
        if not due_at:
            continue
        try:
            due_dt = datetime.fromisoformat(due_at.replace('Z', '+00:00'))
            if due_dt < now:
                overdue.append(t)
        except Exception:
            continue

        if due_dt < now:
            reminder_lines.append(f"⚠️ Overdue: #{task['id']} {task['title']} (due {due_dt.isoformat()})")
        else:
            reminder_lines.append(f"⏰ Due soon: #{task['id']} {task['title']} (due {due_dt.isoformat()})")

    auto_completed = auto_complete_due_tasks()

    if not reminder_lines and auto_completed == 0:
        logger.info("No task reminders needed")
        return

    session_id = "system_tasks"
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    summary = "\n".join(reminder_lines)
    if auto_completed:
        summary = (summary + "\n" if summary else "") + f"✅ Auto-completed tasks at/after due time: {auto_completed}"
    try:
        set_session_category(session_id, "System Tasks")
        history = get_sql_chat_history(session_id)
        history.add_user_message(f"Run task reminder check at {timestamp}")
        history.add_ai_message(f"**Task Reminder Report ({timestamp})**\n{summary}")
        _send_resend_email(
            subject=f"AmpAI Task Reminder Report ({timestamp})",
            body_text=summary,
        )
        logger.info("Task reminders recorded", extra={"reminder_count": len(reminder_lines)})
    except Exception as e:
        logger.exception("Error writing task digest: %s", e)


def run_chat_reply_digest():
    default_window = max(1, int(get_config("notification_default_digest_interval_minutes", "30") or "30"))
    pending = list_pending_reply_notifications_for_digest(max_age_minutes=default_window)
    if not pending:
        return

    grouped = {}
    delivered_ids = []
    for row in pending:
        username = row.get("username") or "unknown"
        grouped.setdefault(username, []).append(row)
        delivered_ids.append(int(row["id"]))

    lines = []
    for username, entries in grouped.items():
        lines.append(f"User: {username} ({len(entries)} replies)")
        for entry in entries[:20]:
            created_at = entry.get("created_at")
            lines.append(
                f"- [{created_at}] Session {entry.get('session_id')}: {(entry.get('reply_preview') or '')[:140]}"
            )
        lines.append("")

    body = "AmpAI periodic chat reply digest\n\n" + "\n".join(lines).strip()
    sent = _send_resend_email(subject="AmpAI Chat Reply Digest", body_text=body)
    if sent:
        mark_pending_reply_notifications_delivered(delivered_ids)
    else:
        logger.warning("Reply digest email not sent; pending items retained")


def run_memory_summarizer():
    min_age_days = max(7, int(get_config("memory_summarizer_min_age_days", "14") or "14"))
    min_group_size = max(2, int(get_config("memory_summarizer_min_group_size", "3") or "3"))
    result = summarize_approved_memories(min_age_days=min_age_days, min_group_size=min_group_size, max_groups=200)
    logger.info(
        "Memory summarizer run complete",
        extra={
            "groups_created": int(result.get("groups_created", 0)),
            "sources_marked": int(result.get("sources_marked", 0)),
        },
    )


def run_curator_nudges():
    due_tasks = list_tasks(status='todo')
    now = datetime.now(timezone.utc)
    enable = str(get_config("curator_nudges_enabled", "true") or "true").strip().lower() in {"1", "true", "yes", "on"}
    if not enable:
        return
    for task in due_tasks[:100]:
        due_at = task.get("due_at")
        if not due_at:
            continue
        try:
            due_dt = datetime.fromisoformat(str(due_at).replace("Z", "+00:00"))
        except Exception:
            continue
        if due_dt > now:
            continue
        create_curator_nudge(
            username=task.get("username") or "admin",
            session_id=task.get("session_id"),
            nudge_type="overdue_task",
            payload={
                "task_id": task.get("id"),
                "title": task.get("title"),
                "due_at": due_dt.isoformat(),
                "message": f"Task '{task.get('title')}' is overdue. Do you want me to create a follow-up plan?",
            },
        )


def run_skill_rollout_guard():
    for skill in list_agent_skills(limit=300):
        skill_id = int(skill.get("id"))
        raw = (get_config(f"skill_rollout_{skill_id}", "") or "").strip()
        if not raw:
            continue
        try:
            rollout = json.loads(raw)
        except Exception:
            continue
        if rollout.get("status") != "canary":
            continue
        perf = get_skill_performance(skill_id=skill_id, lookback_days=7)
        if perf.get("runs", 0) < 5:
            continue
        if perf.get("success_rate", 0.0) < 0.6:
            rollout["status"] = "rolled_back_auto"
            rollout["ended_at"] = datetime.now(timezone.utc).isoformat()
            set_config(f"skill_rollout_{skill_id}", json.dumps(rollout))
        elif perf.get("success_rate", 0.0) >= 0.75:
            rollout["status"] = "promoted"
            rollout["ended_at"] = datetime.now(timezone.utc).isoformat()
            set_config(f"skill_rollout_{skill_id}", json.dumps(rollout))


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(run_network_sweep, 'cron', hour=9, minute=0)
        scheduler.add_job(run_task_digest, 'interval', minutes=30)
        scheduler.add_job(run_chat_reply_digest, 'interval', minutes=5)
        scheduler.add_job(run_memory_summarizer, 'cron', day_of_week='sun', hour=3, minute=0)
        scheduler.add_job(run_memory_summarizer, 'cron', hour=3, minute=30)
        scheduler.add_job(run_curator_nudges, 'interval', minutes=20)
        scheduler.add_job(run_skill_rollout_guard, 'interval', minutes=30)
        scheduler.start()
        logger.info("Background scheduler started")


def get_scheduler_diagnostics() -> dict:
    """Return a dict compatible with the admin health dashboard."""
    try:
        jobs = [str(j.id) for j in scheduler.get_jobs()] if scheduler.running else []
        return {
            "running": scheduler.running,
            "jobs": jobs,
            "last_run": {},
        }
    except Exception as exc:
        return {"running": False, "jobs": [], "last_run": {}, "error": str(exc)}
