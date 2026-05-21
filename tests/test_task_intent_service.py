"""Tests for services/task_intent_service.py — Task intent detection.

Validates: Requirements 11.1, 11.4, 11.5
"""

import sys
import os
import importlib.util

# Ensure project root is on path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

# Load the module directly to avoid pulling in heavy deps via services/__init__.py
_module_path = os.path.join(_project_root, "services", "task_intent_service.py")
_spec = importlib.util.spec_from_file_location("task_intent_service", _module_path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

import pytest

detect_task_intent = _module.detect_task_intent
extract_due_date = _module.extract_due_date
extract_intent_type = _module.extract_intent_type
generate_task_suggestion = _module.generate_task_suggestion
generate_task_title = _module.generate_task_title
infer_priority = _module.infer_priority
process_chat_for_task_intent = _module.process_chat_for_task_intent


# ── detect_task_intent ────────────────────────────────────────────────────────


class TestDetectTaskIntent:
    """Test detection of task-related intent keywords in messages."""

    @pytest.mark.parametrize(
        "message",
        [
            "I have a todo for tomorrow",
            "Remind me to call the dentist",
            "I need to finish the report by Friday",
            "Let's follow up on this next week",
            "The deadline is next Monday",
            "Add this as an action item",
            "Create a task for the deployment",
            "Don't forget to send the invoice",
            "Make sure to review the PR",
            "Add a task to update the docs",
            "Set a reminder for the meeting",
        ],
    )
    def test_detects_task_keywords(self, message):
        """Messages with task-related keywords should be detected."""
        assert detect_task_intent(message) is True

    @pytest.mark.parametrize(
        "message",
        [
            "What's the weather like today?",
            "Tell me a joke",
            "How does Python handle memory?",
            "What is the capital of France?",
            "",
            "Hello, how are you?",
        ],
    )
    def test_no_false_positives(self, message):
        """Messages without task intent should not be detected."""
        assert detect_task_intent(message) is False

    def test_empty_message(self):
        """Empty or None messages should not trigger detection."""
        assert detect_task_intent("") is False
        assert detect_task_intent(None) is False

    def test_case_insensitive(self):
        """Detection should be case-insensitive."""
        assert detect_task_intent("TODO: fix the bug") is True
        assert detect_task_intent("REMIND ME to call") is True
        assert detect_task_intent("I NEED TO finish this") is True


# ── extract_intent_type ───────────────────────────────────────────────────────


class TestExtractIntentType:
    """Test extraction of intent type from messages."""

    def test_reminder_intent(self):
        assert extract_intent_type("Remind me to call the dentist") == "reminder"

    def test_action_intent(self):
        assert extract_intent_type("I need to finish the report") == "action"

    def test_followup_intent(self):
        assert extract_intent_type("Follow up with the client") == "followup"

    def test_todo_intent(self):
        assert extract_intent_type("Add this to my todo list") == "todo"

    def test_deadline_intent(self):
        assert extract_intent_type("The deadline is Friday") == "deadline"

    def test_no_intent(self):
        assert extract_intent_type("What's the weather?") is None

    def test_empty(self):
        assert extract_intent_type("") is None
        assert extract_intent_type(None) is None


# ── infer_priority ────────────────────────────────────────────────────────────


class TestInferPriority:
    """Test priority inference from message content."""

    def test_urgent_keywords(self):
        assert infer_priority("This is urgent, fix it ASAP") == "urgent"
        assert infer_priority("Critical bug in production") == "urgent"

    def test_high_keywords(self):
        assert infer_priority("This is important for the release") == "high"
        assert infer_priority("Must complete before demo") == "high"

    def test_low_keywords(self):
        assert infer_priority("No rush, do it whenever") == "low"
        assert infer_priority("Low priority cleanup task") == "low"

    def test_default_medium(self):
        assert infer_priority("Remind me to call the dentist") == "medium"
        assert infer_priority("I need to update the docs") == "medium"

    def test_empty(self):
        assert infer_priority("") == "medium"
        assert infer_priority(None) == "medium"


# ── extract_due_date ──────────────────────────────────────────────────────────


class TestExtractDueDate:
    """Test due date extraction from messages."""

    def test_today(self):
        result = extract_due_date("I need to do this today")
        assert result is not None
        # Should be today's date in YYYY-MM-DD format
        from datetime import datetime, timezone

        expected = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert result == expected

    def test_tomorrow(self):
        result = extract_due_date("Remind me tomorrow")
        assert result is not None
        from datetime import datetime, timedelta, timezone

        expected = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
        assert result == expected

    def test_next_week(self):
        result = extract_due_date("Follow up next week")
        assert result is not None
        from datetime import datetime, timedelta, timezone

        expected = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
        assert result == expected

    def test_in_n_days(self):
        result = extract_due_date("Do this in 3 days")
        assert result is not None
        from datetime import datetime, timedelta, timezone

        expected = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d")
        assert result == expected

    def test_no_date(self):
        result = extract_due_date("I need to fix the bug")
        assert result is None

    def test_empty(self):
        assert extract_due_date("") is None
        assert extract_due_date(None) is None


# ── generate_task_title ───────────────────────────────────────────────────────


class TestGenerateTaskTitle:
    """Test task title generation from messages."""

    def test_strips_remind_me_prefix(self):
        title = generate_task_title("Remind me to call the dentist")
        assert "remind me" not in title.lower()
        assert "call the dentist" in title.lower()

    def test_strips_i_need_to_prefix(self):
        title = generate_task_title("I need to finish the report")
        assert "i need to" not in title.lower()
        assert "finish the report" in title.lower()

    def test_strips_todo_prefix(self):
        title = generate_task_title("todo: update the documentation")
        assert title.lower().startswith("update")

    def test_max_length(self):
        long_message = "Remind me to " + "x" * 200
        title = generate_task_title(long_message)
        assert len(title) <= 150

    def test_empty_message(self):
        title = generate_task_title("")
        assert title == "Follow up on conversation"

    def test_none_message(self):
        title = generate_task_title(None)
        assert title == "Follow up on conversation"

    def test_multiline_uses_first_line(self):
        title = generate_task_title("Remind me to call\nAlso check email\nAnd more")
        assert "call" in title.lower()
        assert "email" not in title.lower()


# ── generate_task_suggestion ──────────────────────────────────────────────────


class TestGenerateTaskSuggestion:
    """Test full task suggestion generation."""

    def test_generates_suggestion_for_task_intent(self):
        suggestion = generate_task_suggestion(
            message="Remind me to call the dentist tomorrow",
            session_id="sess-123",
            username="testuser",
        )
        assert suggestion is not None
        assert suggestion["title"]
        assert suggestion["session_id"] == "sess-123"
        assert suggestion["username"] == "testuser"
        assert suggestion["status"] == "pending"
        assert suggestion["source"] == "intent_detection"
        assert suggestion["priority"] == "medium"
        assert suggestion["due_at"] is not None  # "tomorrow" should be extracted
        assert suggestion["id"]  # UUID should be generated

    def test_returns_none_for_no_intent(self):
        suggestion = generate_task_suggestion(
            message="What's the weather like?",
            session_id="sess-123",
            username="testuser",
        )
        assert suggestion is None

    def test_priority_inference(self):
        suggestion = generate_task_suggestion(
            message="I need to fix this urgent bug ASAP",
            session_id="sess-123",
            username="testuser",
        )
        assert suggestion is not None
        assert suggestion["priority"] == "urgent"

    def test_description_max_length(self):
        long_message = "I need to " + "x" * 1500
        suggestion = generate_task_suggestion(
            message=long_message,
            session_id="sess-123",
            username="testuser",
        )
        assert suggestion is not None
        assert len(suggestion["description"]) <= 1000


# ── process_chat_for_task_intent ──────────────────────────────────────────────


class TestProcessChatForTaskIntent:
    """Test the main chat pipeline integration function."""

    def test_returns_suggestions_for_task_intent(self):
        suggestions = process_chat_for_task_intent(
            message="Remind me to send the invoice",
            session_id="sess-123",
            username="testuser",
        )
        assert len(suggestions) == 1
        assert suggestions[0]["title"]
        assert suggestions[0]["session_id"] == "sess-123"

    def test_returns_empty_for_no_intent(self):
        suggestions = process_chat_for_task_intent(
            message="Hello, how are you?",
            session_id="sess-123",
            username="testuser",
        )
        assert suggestions == []

    def test_avoids_duplicate_titles(self):
        existing = [{"title": "send the invoice", "id": "existing-1"}]
        suggestions = process_chat_for_task_intent(
            message="Remind me to send the invoice",
            session_id="sess-123",
            username="testuser",
            existing_suggestions=existing,
        )
        assert suggestions == []

    def test_empty_message(self):
        suggestions = process_chat_for_task_intent(
            message="",
            session_id="sess-123",
            username="testuser",
        )
        assert suggestions == []

    def test_suggestion_linked_to_session(self):
        """On approval: task should be linked to source session (Req 11.4)."""
        suggestions = process_chat_for_task_intent(
            message="I need to follow up with the client next week",
            session_id="sess-456",
            username="testuser",
        )
        assert len(suggestions) == 1
        assert suggestions[0]["session_id"] == "sess-456"
        assert suggestions[0]["status"] == "pending"
        # Due date should be extracted from "next week"
        assert suggestions[0]["due_at"] is not None
