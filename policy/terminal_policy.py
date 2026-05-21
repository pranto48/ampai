"""Terminal command security validation policy.

Implements dangerous pattern detection, denylist/allowlist enforcement
(denylist takes precedence), and allowed folder restrictions for the
Terminal_Executor subsystem.

Requirements: 9.3, 9.4, 9.5
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_LIST_ENTRIES = 500

# Dangerous command patterns that are always blocked regardless of allowlist.
# These cover destructive filesystem operations, system shutdown, credential
# dumping, keylogging, and stealth monitoring across macOS/Linux/Windows.
DANGEROUS_PATTERNS: List[re.Pattern[str]] = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"rm\s+(-rf?|--recursive)\s+/",
        r"\bformat\b",
        r"del\s+/[sS]",
        r"Remove-Item.*-Recurse.*(C:\\|/|\\Windows|\\System32)",
        r"\bshutdown\b",
        r"\bregedit\b|\breg\s+(add|delete)\b",
        r"mimikatz|sekurlsa|lsadump|credential.dump",
        r"token.dump|access.token.export",
        r"browser.*password.*export|chrome.*login.*data",
        r"keylog|key.?logger",
        r"stealth|hidden.*monitor",
    ]
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of command security validation."""

    allowed: bool
    blocked: bool = False
    block_reason: Optional[str] = None
    matched_pattern: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Policy class
# ---------------------------------------------------------------------------


class TerminalPolicy:
    """Validates terminal commands against security rules.

    Enforcement order:
    1. Dangerous patterns (always blocked)
    2. Denylist (blocked if matched, takes precedence over allowlist)
    3. Allowlist (if non-empty, command must match at least one entry)
    4. Allowed folders (command working directory must be within approved paths)
    """

    def __init__(
        self,
        denylist: Optional[List[str]] = None,
        allowlist: Optional[List[str]] = None,
        allowed_folders: Optional[List[str]] = None,
    ) -> None:
        self._denylist: List[str] = self._truncate_list(denylist or [])
        self._allowlist: List[str] = self._truncate_list(allowlist or [])
        self._allowed_folders: List[str] = allowed_folders or []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def denylist(self) -> List[str]:
        return list(self._denylist)

    @property
    def allowlist(self) -> List[str]:
        return list(self._allowlist)

    @property
    def allowed_folders(self) -> List[str]:
        return list(self._allowed_folders)

    def set_denylist(self, entries: List[str]) -> None:
        """Replace the denylist (max 500 entries)."""
        self._denylist = self._truncate_list(entries)

    def set_allowlist(self, entries: List[str]) -> None:
        """Replace the allowlist (max 500 entries)."""
        self._allowlist = self._truncate_list(entries)

    def set_allowed_folders(self, folders: List[str]) -> None:
        """Replace the allowed folders list."""
        self._allowed_folders = list(folders)

    def validate_command(self, command: str, working_directory: Optional[str] = None) -> ValidationResult:
        """Validate a command against all security rules.

        Args:
            command: The shell command string to validate.
            working_directory: The directory the command will execute in.

        Returns:
            ValidationResult indicating whether the command is allowed.
        """
        # 1. Check dangerous patterns (always blocked)
        dangerous_match = self._check_dangerous_patterns(command)
        if dangerous_match is not None:
            return ValidationResult(
                allowed=False,
                blocked=True,
                block_reason="Command blocked by security policy: matches dangerous pattern",
                matched_pattern=dangerous_match,
            )

        # 2. Check denylist (takes precedence over allowlist)
        if self._matches_denylist(command):
            return ValidationResult(
                allowed=False,
                blocked=True,
                block_reason="Command blocked by security policy: matches denylist entry",
            )

        # 3. Check allowlist (if non-empty, command must match)
        if self._allowlist and not self._matches_allowlist(command):
            return ValidationResult(
                allowed=False,
                blocked=True,
                block_reason="Command blocked by security policy: not in allowlist",
            )

        # 4. Check allowed folders
        if not self._is_in_allowed_folder(command, working_directory):
            return ValidationResult(
                allowed=False,
                blocked=True,
                block_reason="Command blocked by security policy: path is not permitted",
            )

        return ValidationResult(allowed=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _truncate_list(entries: List[str]) -> List[str]:
        """Enforce maximum list size of 500 entries."""
        return entries[:MAX_LIST_ENTRIES]

    @staticmethod
    def _check_dangerous_patterns(command: str) -> Optional[str]:
        """Return the matched dangerous pattern string, or None if safe."""
        for pattern in DANGEROUS_PATTERNS:
            if pattern.search(command):
                return pattern.pattern
        return None

    def _matches_denylist(self, command: str) -> bool:
        """Return True if command matches any denylist entry."""
        cmd_lower = command.lower()
        for entry in self._denylist:
            if entry.lower() in cmd_lower:
                return True
        return False

    def _matches_allowlist(self, command: str) -> bool:
        """Return True if command matches any allowlist entry."""
        cmd_lower = command.lower()
        for entry in self._allowlist:
            if entry.lower() in cmd_lower:
                return True
        return False

    def _is_in_allowed_folder(self, command: str, working_directory: Optional[str] = None) -> bool:
        """Check if the working directory and any paths in the command are within allowed folders.

        If no allowed_folders are configured, all paths are permitted.
        """
        if not self._allowed_folders:
            return True

        # Check working directory
        if working_directory:
            if not self._path_is_within_allowed(working_directory):
                return False

        # Check for path references in the command itself
        paths_in_command = self._extract_paths_from_command(command)
        for path_str in paths_in_command:
            if not self._path_is_within_allowed(path_str):
                return False

        return True

    def _path_is_within_allowed(self, path_str: str) -> bool:
        """Check if a given path is within any of the allowed folders."""
        try:
            target = Path(path_str).resolve()
        except (OSError, ValueError):
            # If we can't resolve the path, reject it for safety
            return False

        for folder in self._allowed_folders:
            try:
                allowed = Path(folder).resolve()
                if target == allowed or allowed in target.parents:
                    return True
            except (OSError, ValueError):
                continue

        return False

    @staticmethod
    def _extract_paths_from_command(command: str) -> List[str]:
        """Extract absolute path references from a command string.

        Only checks for absolute paths (starting with / or drive letter on Windows)
        since relative paths are resolved against the working directory which is
        already validated separately.
        """
        paths: List[str] = []

        # Match Unix absolute paths: /something
        unix_paths = re.findall(r'(?:^|\s)(/[^\s;|&><"\']+)', command)
        paths.extend(unix_paths)

        # Match Windows absolute paths: C:\something or C:/something
        win_paths = re.findall(r'(?:^|\s)([A-Za-z]:[\\\/][^\s;|&><"\']*)', command)
        paths.extend(win_paths)

        return paths
