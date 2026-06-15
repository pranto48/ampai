import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

# Set up paths so we can import services
sys.path.insert(0, os.path.abspath("."))

from services.browser_automation_service import (
    BrowserAutomationService,
    BrowserConfig,
    BrowserActionStatus
)
from policy.browser_policy import BrowserPolicy

async def test_diagnose():
    config = BrowserConfig(
        enabled=True,
        headless=False,
        domain_allowlist=["example.com", "test.org"],
    )
    policy = BrowserPolicy(domain_allowlist=["example.com", "test.org"])
    service = BrowserAutomationService(
        config=config,
        audit_logger=MagicMock(),
        browser_policy=policy,
    )
    
    # Mock the browser exactly like the test
    service._browser = MagicMock()
    mock_page = AsyncMock()
    mock_page.url = "https://example.com/login"
    mock_page.fill = AsyncMock()
    mock_page.is_closed = MagicMock(return_value=False)
    service._page = mock_page
    service._context = MagicMock()
    
    result = await service.type_text(
        selector="input[type=password]",
        text="secret123",
        username="user1",
        credentials_provided=True,
    )
    print("STATUS:", result.status)
    print("MESSAGE:", result.message)

if __name__ == "__main__":
    asyncio.run(test_diagnose())
