import asyncio
import os
import sys
import traceback
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath("."))

from services.browser_automation_service import (
    BrowserAutomationService,
    BrowserConfig
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
    
    service._browser = MagicMock()
    mock_page = AsyncMock()
    mock_page.url = "https://example.com/login"
    mock_page.fill = AsyncMock()
    mock_page.is_closed = MagicMock(return_value=False)
    service._page = mock_page
    service._context = MagicMock()
    
    try:
        # Call _execute_with_timeout directly
        async def _do_type():
            await mock_page.fill("input", "secret")
        
        await service._execute_with_timeout(_do_type, "type")
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_diagnose())
