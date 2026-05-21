"""Task intent detection service for the chat pipeline.

Detects task-related intent keywords in user messages and generates
task suggestions with title, description, priority, and optional due date.

Requirements: 11.1, 11.4, 11.5
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ampai")

# ── Intent detection patterns ─────────────────────────────────────────────────
# These patterns detect task-related intent in user messages.
# Ordered roughly by specificity (more specific first).

TASK_INTENT_PATTERNS: List[Tuple[str, str]] = [
    # Multi-word phrases (higher confidence)
    (r"\bremind me\b", "reminder"),
    (r"\bi need to\b", "action"),
    (r"\bfollow up\b", "followup"),
    (r"\baction item\b", "action"),
    (r"\bdon'?t forget\b", "reminder"),
    (r"\bmake sure (to|i)\b", "action"),
    (r"\bset a reminder\b", "reminder"),
    (r"\badd (a |to )?task\b", "action"),
    (r"\bschedule (a |to )?\b", "schedule"),
    # Single keywords
    (r"\btodo\b", "todo"),
    (r"\bto-do\b", "todo"),
    (r"\bdeadline\b", "deadline"),
    (r"\btask\b", "todo"),
]

# Priority inference patterns
PRIORITY_PATTERNS: List[Tuple[str, str]] = [
    (r"\b(urgent|asap|immediately|critical|emergency)\b", "urgent"),
    (r"\b(important|high priority|must|crucial)\b", "high"),
    (r"\b(low priority|whenever|no rush|eventually|someday)\b", "low"),
]

# Due date extraction patterns
DUE_DATE_PATTERNS: List[Tuple[str, int]] = [
    (r"\btoday\b", 0),
    (r"\btomorrow\b", 1),
    (r"\bnext week\b", 7),
    (r"\bin (\d+) days?\b", -1),  # -1 means use captured group
    (r"\bby (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", -2),  # -2 means resolve weekday
    (r"\bend of (the )?week\b", -3),  # -3 means end of current week (Friday)
    (r"\bend of (the )?month\b", -4),  # -4 means end of current month
]

WEEKDAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def detect_task_intent(message: str) -> bool:
    """Check if a message contains task-related intent keywords.

    Returns True if any task intent pattern matches.
    """
    if not message:
        return False
    text_lower = message.lower()
    return any(re.search(pattern, text_lower) for pattern, _ in TASK_INTENT_PATTERNS)


def extract_intent_type(message: str) -> Optional[str]:
    """Extract the type of task intent detected (todo, reminder, action, etc.)."""
    if not message:
        return None
    text_lower = message.lower()
    for pattern, intent_type in TASK_INTENT_PATTERNS:
        if re.search(pattern, text_lower):
            return intent_type
    return None


def infer_priority(message: str) -> str:
    """Infer task priority from message content. Defaults to 'medium'."""
    if not message:
        return "medium"
    text_lower = message.lower()
    for pattern, priority in PRIORITY_PATTERNS:
        if re.search(pattern, text_lower):
            return priority
    return "medium"


def extract_due_date(message: str) -> Optional[str]:
    """Extract a due date from the message text. Returns ISO format string or None."""
    if not message:
        return None
    text_lower = message.lower()
    now = datetime.now(timezone.utc)

    for pattern, offset in DUE_DATE_PATTERNS:
        match = re.search(pattern, text_lower)
        if not match:
            continue

        if offset >= 0:
            # Fixed offset in days
            due = now + timedelta(days=offset)
            return due.strftime("%Y-%m-%d")
        elif offset == -1:
            # Dynamic days from captured group
            days = int(match.group(1))
            due = now + timedelta(days=days)
            return due.strftime("%Y-%m-%d")
        elif offset == -2:
            # Resolve weekday
            target_day_name = match.group(1).lower()
            target_weekday = WEEKDAY_MAP.get(target_day_name)
            if target_weekday is not None:
                current_weekday = now.weekday()
                days_ahead = target_weekday - current_weekday
                if days_ahead <= 0:
                    days_ahead += 7
                due = now + timedelta(days=days_ahead)
                return due.strftime("%Y-%m-%d")
        elif offset == -3:
            # End of week (Friday)
            current_weekday = now.weekday()
            days_to_friday = 4 - current_weekday
            if days_to_friday <= 0:
                days_to_friday += 7
            due = now + timedelta(days=days_to_friday)
            return due.strftime("%Y-%m-%d")
        elif offset == -4:
            # End of month
            if now.month == 12:
                due = now.replace(year=now.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                due = now.replace(month=now.month + 1, day=1) - timedelta(days=1)
            return due.strftime("%Y-%m-%d")

    return None


def generate_task_title(message: str) -> str:
    """Generate a concise task title from the user message.

    Extracts the actionable part of the message, stripping common prefixes.
    """
    if not message:
        return "Follow up on conversation"

    text = message.strip()

    # Remove common intent prefixes to get the actionable content
    prefix_patterns = [
        r"^(remind me to |i need to |don'?t forget to |make sure (to |i )|"
        r"add (a )?task (to |for )?|set a reminder (to |for )?|"
        r"follow up (on |with |about )?|todo:?\s*|task:?\s*)",
    ]
    cleaned = text
    for pattern in prefix_patterns:
        cleaned = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE).strip()

    # Use the cleaned text as title, truncated to 150 chars
    title = cleaned if cleaned else text
    # Take first sentence or line
    first_line = title.split("\n")[0].strip()
    first_sentence = re.split(r"[.!?]", first_line)[0].strip()

    result = first_sentence if first_sentence else first_line
    return result[:150] if result else "Follow up on conversation"


def generate_task_suggestion(
    message: str,
    session_id: str,
    username: str,
    response_text: str = "",
) -> Optional[Dict[str, Any]]:
    """Generate a task suggestion from a message with detected task intent.

    Returns a suggestion dict with id, title, description, priority, due_at,
    session_id, username, status, and source. Returns None if no intent detected.
    """
    if not detect_task_intent(message):
        return None

    title = generate_task_title(message)
    priority = infer_priority(message)
    due_at = extract_due_date(message)
    intent_type = extract_intent_type(message)

    # Build description from the original message context
    description = message.strip()[:1000]

    suggestion = {
        "id": str(uuid.uuid4()),
        "title": title,
        "description": description,
        "priority": priority,
        "due_at": due_at,
        "session_id": session_id,
        "username": username,
        "status": "pending",
        "source": "intent_detection",
        "intent_type": intent_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resolved": False,
        "task_id": None,
        "resolved_at": None,
    }

    return suggestion


def process_chat_for_task_intent(
    message: str,
    session_id: str,
    username: str,
    response_text: str = "",
    existing_suggestions: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Process a chat message for task intent and return any new suggestions.

    This is the main entry point called from the chat pipeline.
    It detects intent, generates suggestions, and avoids duplicates.

    Returns a list of new task suggestions (may be empty).
    """
    if not message:
        return []

    # Check if intent is detected
    if not detect_task_intent(message):
        return []

    # Generate suggestion
    suggestion = generate_task_suggestion(
        message=message,
        session_id=session_id,
        username=username,
        response_text=response_text,
    )

    if not suggestion:
        return []

    # Avoid duplicate suggestions for very similar titles in the same session
    if existing_suggestions:
        new_title_lower = suggestion["title"].lower().strip()
        for existing in existing_suggestions:
            existing_title = (existing.get("title") or "").lower().strip()
            if existing_title and existing_title == new_title_lower:
                return []

    return [suggestion]
