#!/usr/bin/env python3
"""Static connection sanity checks for frontend/backend integration.

Checks:
1) Frontend fetch('/api/...') endpoints are present in backend FastAPI routes.
2) Required env examples include DATABASE_URL and REDIS_URL guidance.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FRONTEND_FILES = [
    ROOT / "frontend" / "app.js",
    ROOT / "frontend" / "admin.js",
    ROOT / "frontend" / "auth.js",
    ROOT / "frontend" / "memory-explorer.js",
    ROOT / "frontend" / "build" / "index.js",
    ROOT / "frontend" / "index.tsx",
]

BACKEND_MAIN = ROOT / "backend" / "main.py"


def extract_frontend_endpoints() -> set[str]:
    pattern = re.compile(r"fetch\(\s*`?['\"](/api[^'\"`?)]*)")
    endpoints: set[str] = set()
    for path in FRONTEND_FILES:
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            endpoint = match.group(1)
            endpoint = endpoint.replace("${encodeURIComponent(username)}", "{username}")
            endpoint = endpoint.replace("${selectedGroupId}", "{id}")
            endpoint = endpoint.replace("${encodeURIComponent(sessionId)}", "{session_id}")
            endpoint = endpoint.replace("${taskId}", "{task_id}")
            endpoint = endpoint.replace("${sessionId}", "{session_id}")
            endpoints.add(endpoint.split("?")[0])
    return endpoints


def extract_backend_routes() -> set[str]:
    text = BACKEND_MAIN.read_text(encoding="utf-8")
    return set(re.findall(r"@app\.(?:get|post|put|patch|delete)\(\"([^\"]+)\"", text))


def route_matches(endpoint: str, route: str) -> bool:
    regex = re.sub(r"\{[^}]+\}", r"[^/]+", route)
    return re.fullmatch(regex, endpoint) is not None


def check_env_examples() -> list[str]:
    errors: list[str] = []
    dyad = (ROOT / ".env.dyad.example").read_text(encoding="utf-8")
    example = (ROOT / ".env.example").read_text(encoding="utf-8")

    if "DATABASE_URL=" not in dyad:
        errors.append(".env.dyad.example is missing DATABASE_URL")
    if "REDIS_URL=" not in dyad:
        errors.append(".env.dyad.example is missing REDIS_URL")
    if "REDIS_PASSWORD=" not in example:
        errors.append(".env.example is missing REDIS_PASSWORD")

    return errors


def main() -> int:
    frontend_endpoints = extract_frontend_endpoints()
    backend_routes = extract_backend_routes()

    missing = []
    for endpoint in sorted(frontend_endpoints):
        if endpoint in backend_routes:
            continue
        if any(route_matches(endpoint, route) for route in backend_routes):
            continue
        missing.append(endpoint)

    print(f"Frontend endpoints checked: {len(frontend_endpoints)}")
    print(f"Backend routes discovered: {len(backend_routes)}")

    if missing:
        print("\nMissing backend routes for frontend endpoints:")
        for endpoint in missing:
            print(f"  - {endpoint}")

    env_errors = check_env_examples()
    if env_errors:
        print("\nEnvironment example issues:")
        for error in env_errors:
            print(f"  - {error}")

    if missing or env_errors:
        return 1

    print("\nAll static connection checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
