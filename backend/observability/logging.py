from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger("ampai.operations")


def emit_structured(event: str, trace_id: str, **fields: Any) -> None:
    payload: Dict[str, Any] = {
        "event": event,
        "trace_id": trace_id,
        **fields,
    }
    logger.info(payload)
