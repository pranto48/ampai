import ftplib
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from io import BytesIO
from typing import Dict, List, Optional, Tuple


def build_backup_payload(sessions: List[Dict], actor: str) -> Tuple[str, Dict]:
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "by": actor,
        "sessions": sessions,
    }
    serialized = json.dumps(payload, indent=2)
    message_count = sum(len(s.get("messages", [])) for s in sessions)
    checksum = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    manifest = {
        "timestamp": payload["created_at"],
        "session_count": len(sessions),
        "message_count": message_count,
        "checksum_sha256": checksum,
    }
    return serialized, manifest


def write_backup_local(local_dir: str, filename: str, serialized: str, manifest: Dict) -> Dict:
    os.makedirs(local_dir, exist_ok=True)
    payload_path = os.path.join(local_dir, filename)
    manifest_path = os.path.join(local_dir, filename.replace(".json", ".manifest.json"))
    with open(payload_path, "w", encoding="utf-8") as f:
        f.write(serialized)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return {"mode": "local", "path": payload_path, "manifest_path": manifest_path}


def write_backup_ftp(host: str, user: str, password: str, remote_path: str, filename: str, serialized: str, manifest: Dict) -> Dict:
    manifest_name = filename.replace(".json", ".manifest.json")
    with ftplib.FTP(host) as ftp:
        ftp.login(user=user, passwd=password)
        ftp.cwd(remote_path or "/")
        ftp.storbinary(f"STOR {filename}", BytesIO(serialized.encode("utf-8")))
        ftp.storbinary(f"STOR {manifest_name}", BytesIO(json.dumps(manifest, indent=2).encode("utf-8")))
    return {"mode": "ftp", "file": filename, "manifest_file": manifest_name}


def _run_smbclient(command: List[str], timeout: int = 25) -> subprocess.CompletedProcess:
    return subprocess.run(command, text=True, capture_output=True, timeout=timeout)


def test_smb_connection(host: str, share: str, username: str, password: str, domain: str = "") -> Tuple[bool, str]:
    cmd = ["smbclient", f"//{host}/{share}", "-U", f"{username}%{password}", "-c", "ls"]
    if domain:
        cmd.extend(["-W", domain])
    try:
        result = _run_smbclient(cmd)
    except FileNotFoundError:
        return False, "smbclient not found on server"
    except Exception as exc:
        return False, str(exc)
    if result.returncode == 0:
        return True, "SMB connection successful"
    return False, (result.stderr or result.stdout or "SMB connection failed").strip()


def write_backup_smb(
    host: str,
    share: str,
    remote_path: str,
    username: str,
    password: str,
    domain: str,
    filename: str,
    serialized: str,
    manifest: Dict,
) -> Dict:
    manifest_name = filename.replace(".json", ".manifest.json")
    remote_path = (remote_path or "").strip().strip("/")
    with tempfile.TemporaryDirectory(prefix="ampai_backup_") as tmp:
        payload_file = os.path.join(tmp, filename)
        manifest_file = os.path.join(tmp, manifest_name)
        with open(payload_file, "w", encoding="utf-8") as f:
            f.write(serialized)
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        command_parts = []
        if remote_path:
            command_parts.append(f"mkdir {remote_path}")
            command_parts.append(f"cd {remote_path}")
        command_parts.append(f"put {payload_file} {filename}")
        command_parts.append(f"put {manifest_file} {manifest_name}")
        cmd = ["smbclient", f"//{host}/{share}", "-U", f"{username}%{password}", "-c", "; ".join(command_parts)]
        if domain:
            cmd.extend(["-W", domain])
        try:
            result = _run_smbclient(cmd, timeout=60)
        except FileNotFoundError as exc:
            raise RuntimeError("smbclient not found on server") from exc
        except Exception as exc:
            raise RuntimeError(f"SMB backup failed: {exc}") from exc
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "SMB backup failed").strip())
    return {"mode": "smb", "file": filename, "manifest_file": manifest_name, "remote_path": remote_path or "/"}


def test_ftp_connection(host: str, user: str, password: str, remote_path: Optional[str] = "/") -> Tuple[bool, str]:
    try:
        with ftplib.FTP(host, timeout=10) as ftp:
            ftp.login(user=user, passwd=password)
            if remote_path:
                ftp.cwd(remote_path)
        return True, "FTP connection successful"
    except Exception as exc:
        return False, str(exc)
