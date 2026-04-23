import subprocess
import re
import logging
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
logger = logging.getLogger("ampai.scheduler")


def ping_target(ip_address: str) -> dict:
    try:
        result = subprocess.run(['ping', '-c', '3', '-W', '2', ip_address], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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

    if not overdue:
        return

    session_id = "system_tasks"
    report = "Overdue tasks:\n" + "\n".join([f"- [{t['priority']}] {t['title']} (due {t['due_at']})" for t in overdue[:30]])
    try:
        set_session_category(session_id, "System Tasks")
        history = get_sql_chat_history(session_id)
        history.add_user_message(f"Run task reminder check at {timestamp}")
        history.add_ai_message(f"**Task Reminder Report ({timestamp})**\n{summary}")
        logger.info("Task reminders recorded", extra={"reminder_count": len(reminder_lines)})
    except Exception as e:
        logger.exception("Error writing task digest: %s", e)


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(run_network_sweep, 'cron', hour=9, minute=0)
        scheduler.add_job(run_task_digest, 'interval', minutes=30)
        scheduler.start()
        logger.info("Background scheduler started")
