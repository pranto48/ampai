from fastapi.testclient import TestClient
from backend import main
import io
import json
import gzip
import zipfile


class DummyUser:
    username = "admin"


def _override_admin():
    return DummyUser()


main.app.dependency_overrides[main.require_admin_user] = _override_admin
client = TestClient(main.app)


def test_restore_upload_valid_zip(monkeypatch):
    monkeypatch.setattr(main, "restore_full_backup", lambda path, opts: {"ok": True, "summary": {"chats": 1}, "errors": []})
    files = {"backup_file": ("backup.zip", b"PK\x03\x04fake", "application/zip")}
    resp = client.post("/api/admin/fullbackup/restore-upload", files=files)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_restore_upload_invalid_extension():
    files = {"backup_file": ("backup.txt", b"notzip", "text/plain")}
    resp = client.post("/api/admin/fullbackup/restore-upload", files=files)
    assert resp.status_code == 400
    assert "zip" in resp.json()["detail"].lower()


def test_restore_upload_empty_file():
    files = {"backup_file": ("backup.zip", b"", "application/zip")}
    resp = client.post("/api/admin/fullbackup/restore-upload", files=files)
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_restore_upload_preflight_only():
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        full_data = {"users": [{"username": "u1"}], "configs": {"a": "b"}}
        zf.writestr("full_data.json.gz", gzip.compress(json.dumps(full_data).encode("utf-8")))
    files = {"backup_file": ("backup.zip", archive.getvalue(), "application/zip")}
    resp = client.post("/api/admin/fullbackup/restore-upload", files=files, data={"preflight_only": "true"})
    assert resp.status_code == 200
    assert resp.json()["preflight"]["users"] == 1


def test_restore_upload_dry_run(monkeypatch):
    monkeypatch.setattr(main, "restore_full_backup", lambda path, opts: {"ok": False})
    files = {"backup_file": ("backup.zip", b"PK\x03\x04fake", "application/zip")}
    resp = client.post("/api/admin/fullbackup/restore-upload", files=files, data={"dry_run": "true"})
    assert resp.status_code == 200
    assert resp.json().get("dry_run") is True


def test_update_version_check_ok_false(monkeypatch):
    monkeypatch.setattr(main, "_get_current_git_commit", lambda: "unknown")
    monkeypatch.setattr(main, "_fetch_remote_commit", lambda: "abc123")
    resp = client.get("/api/admin/update/version")
    assert resp.status_code == 200
    data = resp.json()
    assert data["check_ok"] is False
    assert data["up_to_date"] is False


def test_update_version_check_ok_true(monkeypatch):
    monkeypatch.setattr(main, "_get_current_git_commit", lambda: "abc123")
    monkeypatch.setattr(main, "_fetch_remote_commit", lambda: "abc123999")
    resp = client.get("/api/admin/update/version")
    assert resp.status_code == 200
    data = resp.json()
    assert data["check_ok"] is True
    assert data["up_to_date"] is True


def test_settings_export_default_redacts_secrets(monkeypatch):
    monkeypatch.setattr(main, "get_all_configs", lambda: {"openai_api_key": "secret", "chat_agent_name": "Amp"})
    resp = client.get("/api/admin/settings/export")
    assert resp.status_code == 200
    body = resp.json()
    assert body["configs"] == {"chat_agent_name": "Amp"}
    assert "openai_api_key" in body["meta"]["redacted_keys"]


def test_settings_export_secrets_requires_confirmation():
    resp = client.get("/api/admin/settings/export?include_secrets=true")
    assert resp.status_code == 400


def test_settings_import_dry_run_skip_conflicts(monkeypatch):
    monkeypatch.setattr(main, "get_all_configs", lambda: {"a": "1", "b": "2"})
    set_calls = []
    monkeypatch.setattr(main, "set_config", lambda key, value: set_calls.append((key, value)))
    payload = {"configs": {"a": "9", "b": "2", "c": "3"}, "dry_run": True, "conflict_strategy": "skip"}
    resp = client.post("/api/admin/settings/import", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["created"] == 1
    assert data["summary"]["skipped_conflict"] == 1
    assert data["summary"]["unchanged"] == 1
    assert set_calls == []


def test_settings_import_apply_overwrite(monkeypatch):
    monkeypatch.setattr(main, "get_all_configs", lambda: {"a": "1"})
    set_calls = []
    monkeypatch.setattr(main, "set_config", lambda key, value: set_calls.append((key, value)))
    payload = {"configs": {"a": "2", "b": "3"}, "dry_run": False, "conflict_strategy": "overwrite"}
    resp = client.post("/api/admin/settings/import", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["updated"] == 1
    assert data["summary"]["created"] == 1
    assert ("a", "2") in set_calls
    assert ("b", "3") in set_calls
