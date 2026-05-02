from fastapi.testclient import TestClient
from backend import main


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
