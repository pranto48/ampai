import os
import json
import subprocess
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List

_update_lock = threading.Lock()

STATUS_FILE = "/data/agent_data/update_status.json"
LOG_FILE = "/data/agent_data/update.log"
RESULT_FILE = "/data/agent_data/update_result.txt"
REPO_URL = os.getenv("AMPAI_REPO_URL", "https://github.com/pranto48/ampai.git")

def get_current_git_commit() -> str:
    try:
        candidates = [
            "/app/.git",
            "/app_host/.git",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), ".git"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", ".git"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "..", ".git"),
        ]
        for candidate in candidates:
            if os.path.isdir(candidate):
                git_head = os.path.join(candidate, "HEAD")
                if os.path.exists(git_head):
                    with open(git_head) as f:
                        ref = f.read().strip()
                    if ref.startswith("ref: "):
                        ref_file = os.path.join(candidate, ref[5:])
                        if os.path.exists(ref_file):
                            with open(ref_file) as f:
                                return f.read().strip()[:12]
                    return ref[:12]
    except Exception:
        pass
    return "unknown"

def extract_github_slug(repo_url: str) -> Any:
    url = (repo_url or "").strip()
    if not url:
        return None
    if url.startswith("git@github.com:"):
        slug = url.split(":", 1)[1]
    elif "github.com/" in url:
        slug = url.split("github.com/", 1)[1]
    else:
        return None
    slug = slug.strip().rstrip("/")
    if slug.endswith(".git"):
        slug = slug[:-4]
    parts = [p for p in slug.split("/") if p]
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1]}"

def fetch_remote_commit() -> str:
    import urllib.request as _ur
    slug = extract_github_slug(REPO_URL)
    if not slug:
        return "unknown"
    for branch in ["main", "master"]:
        try:
            req = _ur.Request(
                f"https://api.github.com/repos/{slug}/commits/{branch}",
                headers={
                    "Accept": "application/vnd.github.sha",
                    "User-Agent": "ampai-updater/1.0",
                },
            )
            with _ur.urlopen(req, timeout=10) as resp:
                return resp.read().decode().strip()[:12]
        except Exception:
            continue
    return "unknown"

def check_git_update_available() -> bool:
    current = get_current_git_commit()
    latest = fetch_remote_commit()
    if current == "unknown" or latest == "unknown":
        return False
    return current != latest[:len(current)]

def get_system_update_status() -> Dict[str, Any]:
    status = {
        "state": "idle",
        "started_at": None,
        "finished_at": None,
        "error": None,
        "log_lines": []
    }
    
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                status = json.load(f)
        except Exception:
            pass
            
    if os.path.exists(RESULT_FILE):
        try:
            with open(RESULT_FILE, "r", encoding="utf-8") as f:
                outcome = f.read().strip()
                
            logs = []
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r", encoding="utf-8") as lf:
                    logs = lf.readlines()
            
            status["log_lines"] = [line.strip() for line in logs if line.strip()]
            
            if outcome == "SUCCESS":
                status["state"] = "success"
                status["error"] = None
            else:
                status["state"] = "error"
                status["error"] = "Rebuild and container recreation failed. Check update logs."
                
            status["finished_at"] = datetime.now(timezone.utc).isoformat()
            
            os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(status, f)
                
            os.remove(RESULT_FILE)
        except Exception as e:
            status["error"] = f"Failed to parse update result: {e}"
            
    return status

def _do_update_in_thread(actor: str) -> None:
    status = {
        "state": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "error": None,
        "log_lines": ["Starting AmpAI Git & Docker Rebuild update...", f"Triggered by: {actor}"]
    }
    
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f)
        
    with open(LOG_FILE, "w", encoding="utf-8") as lf:
        lf.write("\n".join(status["log_lines"]) + "\n")
        
    def _log(msg: str):
        status["log_lines"].append(msg)
        try:
            with open(STATUS_FILE, "w", encoding="utf-8") as sf:
                json.dump(status, sf)
            with open(LOG_FILE, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
        except Exception:
            pass
            
    try:
        # Step 1: Git Fetch & Reset
        _log("--- Step 1: Fetching and resetting to latest code ---")
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", "/app"], cwd="/app")
        fetch_res = subprocess.run(["git", "fetch", "--all"], cwd="/app", capture_output=True, text=True, timeout=45)
        if fetch_res.returncode != 0:
            raise RuntimeError(f"git fetch failed: {fetch_res.stderr.strip()}")
            
        reset_res = subprocess.run(["git", "reset", "--hard", "origin/main"], cwd="/app", capture_output=True, text=True, timeout=45)
        if reset_res.returncode != 0:
            raise RuntimeError(f"git reset failed: {reset_res.stderr.strip()}")
            
        _log("Git fetch and hard reset to origin/main successful.")
        
        # Step 2: Detect Host Paths
        _log("--- Step 2: Resolving host environment paths ---")
        host_project_path = "/home/it/ampai"
        host_data_path = "ampai_ampai_data"
        
        try:
            inspect_res = subprocess.run(["docker", "inspect", "ampai-server"], capture_output=True, text=True, timeout=15)
            if inspect_res.returncode == 0:
                data = json.loads(inspect_res.stdout)
                if data and "Mounts" in data[0]:
                    for mount in data[0]["Mounts"]:
                        if mount["Destination"] == "/app":
                            host_project_path = mount["Source"]
                        elif mount["Destination"] == "/data":
                            host_data_path = mount.get("Name") or mount["Source"]
            else:
                _log(f"Warning: docker inspect failed: {inspect_res.stderr.strip()}")
        except Exception as inspect_err:
            _log(f"Warning: Failed to execute docker inspect: {inspect_err}")
            
        _log(f"Host Project Path: {host_project_path}")
        _log(f"Host Data Volume/Path: {host_data_path}")
        
        # Step 3: Spawn detached container
        _log("--- Step 3: Triggering container recreation via detached updater ---")
        
        updater_cmd = (
            f"echo 'Running docker compose up -d --build...' >> {LOG_FILE} && "
            f"docker compose up -d --build >> {LOG_FILE} 2>&1 && "
            f"echo 'SUCCESS' > {RESULT_FILE} || "
            f"(echo 'ERROR: Rebuild failed.' >> {LOG_FILE} && echo 'ERROR' > {RESULT_FILE})"
        )
        
        cmd = [
            "docker", "run", "--rm", "-d",
            "-v", "/var/run/docker.sock:/var/run/docker.sock",
            "-v", f"{host_project_path}:{host_project_path}",
            "-v", f"{host_data_path}:/data",
            "-w", host_project_path,
            "docker:cli",
            "sh", "-c", updater_cmd
        ]
        
        spawn_res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if spawn_res.returncode != 0:
            raise RuntimeError(f"Failed to spawn detached updater: {spawn_res.stderr.strip()}")
            
        _log("Rebuilder spawned successfully. Service will restart shortly.")
        
    except Exception as exc:
        _log(f"ERROR during update: {exc}")
        status["state"] = "error"
        status["finished_at"] = datetime.now(timezone.utc).isoformat()
        status["error"] = str(exc)
        try:
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(status, f)
        except Exception:
            pass
            
        try:
            from database import log_audit_event
            log_audit_event(username=actor, action="admin.docker.update.failure", details=str(exc))
        except Exception:
            pass
    finally:
        try:
            _update_lock.release()
        except RuntimeError:
            pass

def trigger_system_update(actor: str) -> Dict[str, Any]:
    if not _update_lock.acquire(blocking=False):
        return {
            "status": "failed",
            "message": "An update is already in progress"
        }
        
    t = threading.Thread(target=_do_update_in_thread, args=(actor,), daemon=True)
    t.start()
    return {
        "status": "started",
        "message": "Update initiated. Poll /api/admin/update/status for progress."
    }
