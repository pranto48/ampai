"""Tests for policy/browser_policy.py.

Validates domain allowlist enforcement for browser automation.
- Empty allowlist blocks all navigation (Requirement 8.3)
- URLs validated against allowlist before browser actions (Requirement 8.10)
"""

import pytest

from policy.browser_policy import BrowserPolicy, BrowserPolicyError


class TestEmptyAllowlistBlocksAll:
    """An empty allowlist blocks all navigation (Requirement 8.3)."""

    def test_none_allowlist_blocks_navigation(self):
        policy = BrowserPolicy(domain_allowlist=None)
        with pytest.raises(BrowserPolicyError, match="allowlist is empty"):
            policy.check_domain("https://example.com")

    def test_empty_list_blocks_navigation(self):
        policy = BrowserPolicy(domain_allowlist=[])
        with pytest.raises(BrowserPolicyError, match="allowlist is empty"):
            policy.check_domain("https://google.com")

    def test_whitespace_only_entries_treated_as_empty(self):
        policy = BrowserPolicy(domain_allowlist=["", "  ", "\t"])
        with pytest.raises(BrowserPolicyError, match="allowlist is empty"):
            policy.check_domain("https://example.com")

    def test_is_empty_property_true_for_empty_list(self):
        policy = BrowserPolicy(domain_allowlist=[])
        assert policy.is_empty is True

    def test_is_empty_property_false_for_populated_list(self):
        policy = BrowserPolicy(domain_allowlist=["example.com"])
        assert policy.is_empty is False

    def test_is_url_allowed_returns_false_for_empty_allowlist(self):
        policy = BrowserPolicy(domain_allowlist=[])
        assert policy.is_url_allowed("https://example.com") is False


class TestDomainAllowlistEnforcement:
    """URLs validated against allowlist (Requirement 8.10)."""

    def test_allowed_domain_passes(self):
        policy = BrowserPolicy(domain_allowlist=["example.com"])
        # Should not raise
        policy.check_domain("https://example.com/page")

    def test_disallowed_domain_raises(self):
        policy = BrowserPolicy(domain_allowlist=["example.com"])
        with pytest.raises(BrowserPolicyError, match="not in the permitted allowlist"):
            policy.check_domain("https://evil.com/phish")

    def test_error_includes_domain(self):
        policy = BrowserPolicy(domain_allowlist=["example.com"])
        with pytest.raises(BrowserPolicyError) as exc_info:
            policy.check_domain("https://blocked.org/path")
        assert exc_info.value.domain == "blocked.org"

    def test_subdomain_allowed_when_parent_in_list(self):
        policy = BrowserPolicy(domain_allowlist=["example.com"])
        policy.check_domain("https://sub.example.com/page")

    def test_deep_subdomain_allowed(self):
        policy = BrowserPolicy(domain_allowlist=["example.com"])
        policy.check_domain("https://a.b.c.example.com/page")

    def test_parent_not_allowed_when_only_subdomain_in_list(self):
        policy = BrowserPolicy(domain_allowlist=["sub.example.com"])
        with pytest.raises(BrowserPolicyError):
            policy.check_domain("https://example.com/page")

    def test_case_insensitive_matching(self):
        policy = BrowserPolicy(domain_allowlist=["Example.COM"])
        policy.check_domain("https://EXAMPLE.com/page")

    def test_multiple_domains_in_allowlist(self):
        policy = BrowserPolicy(domain_allowlist=["example.com", "trusted.org"])
        policy.check_domain("https://example.com/a")
        policy.check_domain("https://trusted.org/b")

    def test_domain_not_in_multi_entry_allowlist(self):
        policy = BrowserPolicy(domain_allowlist=["example.com", "trusted.org"])
        with pytest.raises(BrowserPolicyError):
            policy.check_domain("https://other.net/c")

    def test_is_url_allowed_returns_true_for_permitted(self):
        policy = BrowserPolicy(domain_allowlist=["example.com"])
        assert policy.is_url_allowed("https://example.com/page") is True

    def test_is_url_allowed_returns_false_for_blocked(self):
        policy = BrowserPolicy(domain_allowlist=["example.com"])
        assert policy.is_url_allowed("https://blocked.com/page") is False


class TestURLParsing:
    """URL parsing edge cases."""

    def test_url_without_scheme(self):
        policy = BrowserPolicy(domain_allowlist=["example.com"])
        policy.check_domain("example.com/page")

    def test_url_with_port(self):
        policy = BrowserPolicy(domain_allowlist=["localhost"])
        policy.check_domain("http://localhost:8080/api")

    def test_url_with_auth_info(self):
        policy = BrowserPolicy(domain_allowlist=["example.com"])
        policy.check_domain("https://user:pass@example.com/page")

    def test_empty_url_raises(self):
        policy = BrowserPolicy(domain_allowlist=["example.com"])
        with pytest.raises(BrowserPolicyError, match="unable to extract"):
            policy.check_domain("")

    def test_whitespace_url_raises(self):
        policy = BrowserPolicy(domain_allowlist=["example.com"])
        with pytest.raises(BrowserPolicyError, match="unable to extract"):
            policy.check_domain("   ")

    def test_url_with_path_and_query(self):
        policy = BrowserPolicy(domain_allowlist=["example.com"])
        policy.check_domain("https://example.com/path?q=search&page=1")

    def test_url_with_fragment(self):
        policy = BrowserPolicy(domain_allowlist=["example.com"])
        policy.check_domain("https://example.com/page#section")


class TestUpdateAllowlist:
    """Tests for dynamically updating the allowlist."""

    def test_update_replaces_allowlist(self):
        policy = BrowserPolicy(domain_allowlist=["old.com"])
        policy.update_allowlist(["new.com"])
        with pytest.raises(BrowserPolicyError):
            policy.check_domain("https://old.com")
        policy.check_domain("https://new.com")

    def test_update_to_empty_blocks_all(self):
        policy = BrowserPolicy(domain_allowlist=["example.com"])
        policy.update_allowlist([])
        with pytest.raises(BrowserPolicyError, match="allowlist is empty"):
            policy.check_domain("https://example.com")

    def test_allowlist_property_returns_current_list(self):
        policy = BrowserPolicy(domain_allowlist=["Example.COM", "Test.Org"])
        assert policy.allowlist == ["example.com", "test.org"]
