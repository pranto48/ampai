"""Configuration validator for AmpAI server startup.

Detects unsafe default values for security-sensitive environment variables
and blocks startup in production mode. In non-production mode, logs warnings
but allows the server to proceed.

This module MUST be called before any network listener binds.
"""

import logging
import os
import sys

logger = logging.getLogger("ampai.config_validator")

# Known unsafe default values for security-sensitive environment variables.
# If any of these are detected in production, startup is blocked.
UNSAFE_DEFAULTS: dict[str, set[str]] = {
    "JWT_SECRET": {
        "change-me",
        "change-me-for-production",
        "change-this-long-random-secret",
    },
    "AMPAI_DEFAULT_ADMIN_PASSWORD": {
        "P@ssw0rd",
        "change-this",
        "admin123",
    },
    "POSTGRES_PASSWORD": {
        "change-this",
        "ampai",
    },
}


def _is_production() -> bool:
    """Determine if the current environment is production.

    Production mode is indicated by AMPAI_ENV being set to
    "production" or "prod" (case-insensitive). Any other value
    or an unset variable indicates non-production mode.
    """
    env = os.getenv("AMPAI_ENV", "development").strip().lower()
    return env in ("production", "prod")


def validate_config() -> None:
    """Validate configuration for unsafe defaults.

    In production mode:
        - Terminates the process with exit code 1 if any security-sensitive
          variable is set to a known unsafe default value.
        - Logs an error for each unsafe default detected.

    In non-production mode:
        - Logs a warning for each unsafe default detected.
        - Allows startup to proceed.

    This function MUST be called before any network listener (e.g. uvicorn)
    binds, so that no requests are served while configuration is unsafe.
    """
    is_production = _is_production()
    errors: list[str] = []
    warnings: list[str] = []

    for var, unsafe_values in UNSAFE_DEFAULTS.items():
        current = os.getenv(var, "")
        if current in unsafe_values:
            if is_production:
                errors.append(
                    f"{var} is set to unsafe default '{current}'"
                )
            else:
                warnings.append(
                    f"{var} is set to unsafe default (ok for dev)"
                )

    if errors:
        for error in errors:
            logger.error("STARTUP BLOCKED: %s", error)
        sys.exit(1)

    for warning in warnings:
        logger.warning(warning)
