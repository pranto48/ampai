"""Browser domain allowlist policy enforcement.

Validates navigation URLs against a configured domain allowlist.
An empty allowlist blocks all navigation (deny-by-default).
"""

from __future__ import annotations

from urllib.parse import urlparse
from typing import List, Optional


class BrowserPolicyError(Exception):
    """Raised when a browser action violates the domain allowlist policy."""

    def __init__(self, message: str, domain: Optional[str] = None):
        super().__init__(message)
        self.domain = domain


class BrowserPolicy:
    """Enforces domain allowlist for browser automation navigation.

    Rules:
    - An empty allowlist blocks ALL navigation (Requirement 8.3).
    - URLs must have a domain that matches an entry in the allowlist.
    - Subdomains are permitted if the parent domain is in the allowlist
      (e.g., "example.com" allows "sub.example.com").
    - Matching is case-insensitive.
    """

    def __init__(self, domain_allowlist: Optional[List[str]] = None):
        """Initialize with a domain allowlist.

        Args:
            domain_allowlist: List of permitted domains. An empty list or None
                blocks all navigation.
        """
        raw = domain_allowlist or []
        self._allowlist: List[str] = [d.lower().strip() for d in raw if d.strip()]

    @property
    def allowlist(self) -> List[str]:
        """Return the current domain allowlist (lowercase, stripped)."""
        return list(self._allowlist)

    @property
    def is_empty(self) -> bool:
        """Return True if the allowlist is empty (all navigation blocked)."""
        return len(self._allowlist) == 0

    def update_allowlist(self, domains: List[str]) -> None:
        """Replace the current allowlist with a new set of domains.

        Args:
            domains: New list of permitted domains.
        """
        self._allowlist = [d.lower().strip() for d in domains if d.strip()]

    def check_domain(self, url: str) -> None:
        """Validate a URL against the domain allowlist.

        Raises BrowserPolicyError if:
        - The allowlist is empty (all navigation blocked).
        - The URL cannot be parsed or has no valid hostname.
        - The URL's domain is not in the allowlist.

        Args:
            url: The URL to validate.

        Raises:
            BrowserPolicyError: If the domain is not permitted.
        """
        if self.is_empty:
            raise BrowserPolicyError(
                "Navigation blocked: domain allowlist is empty. "
                "No domains are permitted for browser automation.",
                domain=None,
            )

        domain = self._extract_domain(url)
        if not domain:
            raise BrowserPolicyError(
                f"Navigation blocked: unable to extract a valid domain from URL '{url}'.",
                domain=None,
            )

        if not self._is_domain_allowed(domain):
            raise BrowserPolicyError(
                f"Navigation blocked: domain '{domain}' is not in the permitted allowlist.",
                domain=domain,
            )

    def is_url_allowed(self, url: str) -> bool:
        """Check if a URL is allowed without raising an exception.

        Args:
            url: The URL to check.

        Returns:
            True if the URL's domain is in the allowlist, False otherwise.
        """
        try:
            self.check_domain(url)
            return True
        except BrowserPolicyError:
            return False

    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract and normalize the domain from a URL.

        Handles URLs with and without scheme. Strips port numbers.

        Args:
            url: The URL to parse.

        Returns:
            Lowercase domain string, or None if parsing fails.
        """
        if not url or not url.strip():
            return None

        # Ensure the URL has a scheme for proper parsing
        normalized = url.strip()
        if "://" not in normalized:
            normalized = "https://" + normalized

        try:
            parsed = urlparse(normalized)
            hostname = parsed.hostname
            if hostname:
                return hostname.lower()
        except (ValueError, AttributeError):
            pass

        return None

    def _is_domain_allowed(self, domain: str) -> bool:
        """Check if a domain matches any entry in the allowlist.

        Supports exact match and subdomain matching:
        - "example.com" in allowlist permits "example.com" and "sub.example.com"
        - "sub.example.com" in allowlist permits only "sub.example.com"

        Args:
            domain: The lowercase domain to check.

        Returns:
            True if the domain is permitted.
        """
        for allowed in self._allowlist:
            if domain == allowed:
                return True
            # Allow subdomains: "sub.example.com" matches allowlist entry "example.com"
            if domain.endswith("." + allowed):
                return True
        return False
