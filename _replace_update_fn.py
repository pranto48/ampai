"""Script to replace _do_update_in_thread in main.py"""
import os

MAIN_PY = os.path.join(os.path.dirname(__file__), "main.py")

with open(MAIN_PY, "r", encoding="utf-8") as f:
    content = f.read()

# Find the start of _do_update_in_thread
start_marker = "def _do_update_in_thread(actor: str) -> None:"
start_idx = content.find(start_marker)
assert start_idx != -1, "Could not find _do_update_in_thread"

# Find the end - next top-level definition after the function body
rest = content[start_idx:]
lines = rest.split("\n")
end_offset = 0
found_body = False
for i, line in enumerate(lines):
    if i == 0:
        continue
    if line == "" or line.startswith(" ") or line.startswith("\t"):
        found_body = True
        continue
    if found_body and (
        line.startswith("def ")
        or line.startswith("class ")
        or line.startswith("@")
    ):
        end_offset = sum(len(l) + 1 for l in lines[:i])
        break

assert end_offset > 0, "Could not find end of function"

# The new function
new_function = '''def _do_update_in_thread(actor: str) -> None:
    """Run the update process in a background thread.

    Downloads the latest code from the GitHub archive (tar.gz), extracts it,
    backs up current files, applies the update while preserving user data,
    installs dependencies, and restarts the server.
    """
    import subprocess
    import tarfile

    global _update_status
    _update_status = {
        "state": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "error": None,
    }
    _update_log_lines.clear()

    try:
        _update_log("Starting AmpAI code update...")
        _update_log(f"Triggered by: {actor}")
        _update_log(f"Repo: {REPO_URL}")

        # -- Step 1: Create code backup --
        _update_log("--- Step 1: Creating code backup ---")
        os.makedirs(CODE_BACKUP_DIR, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = os.path.join(CODE_BACKUP_DIR, ts)
        os.makedirs(backup_path, exist_ok=True)

        backend_src = os.path.abspath(os.path.dirname(__file__))
        frontend_src = _resolve_frontend_dir() or os.path.join(backend_src, "frontend")

        if os.path.isdir(backend_src):
            shutil.copytree(
                backend_src, os.path.join(backup_path, "backend"), dirs_exist_ok=True
            )
            _update_log("Backed up: backend/")
        if os.path.isdir(frontend_src):
            shutil.copytree(
                frontend_src, os.path.join(backup_path, "frontend"), dirs_exist_ok=True
            )
            _update_log("Backed up: frontend/")

        current_commit = _get_current_git_commit()
        with open(os.path.join(backup_path, "git_commit.txt"), "w") as f:
            f.write(current_commit)
        _update_log(f"Backup created at: {backup_path} (commit: {current_commit})")

        # -- Step 2: Download latest code from GitHub archive --
        _update_log("--- Step 2: Downloading latest code from GitHub ---")

        slug = _extract_github_slug(REPO_URL)
        if not slug:
            raise RuntimeError(f"Cannot extract GitHub slug from REPO_URL: {REPO_URL}")

        # Try main branch first, then master as fallback
        archive_url = None
        for branch in ["main", "master"]:
            candidate_url = f"https://github.com/{slug}/archive/refs/heads/{branch}.tar.gz"
            try:
                req = urllib.request.Request(
                    candidate_url,
                    method="HEAD",
                    headers={"User-Agent": "ampai-updater/1.0"},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status == 200:
                        archive_url = candidate_url
                        _update_log(f"Found archive for branch '{branch}'")
                        break
            except Exception:
                continue

        if not archive_url:
            raise RuntimeError(
                f"Failed to find archive for {slug} on main or master branch"
            )

        _update_log(f"Downloading: {archive_url}")
        temp_tar = tempfile.mktemp(suffix=".tar.gz")
        try:
            urllib.request.urlretrieve(archive_url, temp_tar)
        except Exception as dl_err:
            raise RuntimeError(f"Archive download failed: {dl_err}") from dl_err
        _update_log("Download complete. Extracting...")

        temp_dir = tempfile.mkdtemp()
        try:
            with tarfile.open(temp_tar, "r:gz") as tf:
                tf.extractall(temp_dir)
        except Exception as ext_err:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError(f"Archive extraction failed: {ext_err}") from ext_err
        finally:
            if os.path.exists(temp_tar):
                os.remove(temp_tar)

        # Find extracted root directory (e.g. ampai-main/)
        extracted_dirs = [
            d
            for d in os.listdir(temp_dir)
            if os.path.isdir(os.path.join(temp_dir, d))
        ]
        if not extracted_dirs:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError("Archive extraction yielded no directory")
        extracted_root = os.path.join(temp_dir, extracted_dirs[0])
        _update_log(f"Extracted to: {extracted_root}")

        # -- Copy files, preserving user data --
        PRESERVE_FILES = {".env", "docker-compose.yml"}
        PRESERVE_DIRS = {"data", "agent_data"}
        PRESERVE_EXTENSIONS = {".db", ".db-journal"}

        def _should_preserve(name: str, is_dir: bool = False) -> bool:
            """Return True if this file/dir should NOT be overwritten."""
            if is_dir:
                return name in PRESERVE_DIRS
            if name in PRESERVE_FILES:
                return True
            for ext in PRESERVE_EXTENSIONS:
                if name.endswith(ext):
                    return True
            return False

        updated_app_dir = _runnable_app_dir(extracted_root)
        if not updated_app_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError(
                "Downloaded archive does not contain main.py or backend/main.py"
            )

        _update_log(
            "Copying updated files (preserving .env, *.db, data/, agent_data/, docker-compose.yml)..."
        )
        for dirpath, dirnames, filenames in os.walk(updated_app_dir):
            rel_dir = os.path.relpath(dirpath, updated_app_dir)
            target_dir = (
                os.path.join(backend_src, rel_dir) if rel_dir != "." else backend_src
            )

            # Skip preserved and non-essential directories
            dirnames[:] = [
                d
                for d in dirnames
                if not _should_preserve(d, is_dir=True)
                and d
                not in {
                    ".git",
                    "__pycache__",
                    ".pytest_cache",
                    "node_modules",
                    ".vs",
                }
            ]

            os.makedirs(target_dir, exist_ok=True)

            for fname in filenames:
                if _should_preserve(fname):
                    target_file = os.path.join(target_dir, fname)
                    if os.path.exists(target_file):
                        continue
                if fname.endswith(".pyc"):
                    continue
                src_file = os.path.join(dirpath, fname)
                dst_file = os.path.join(target_dir, fname)
                shutil.copy2(src_file, dst_file)

        # Copy frontend if present in archive
        new_frontend = os.path.join(extracted_root, "frontend")
        if os.path.isdir(new_frontend) and os.path.abspath(
            updated_app_dir
        ) != os.path.abspath(extracted_root):
            shutil.copytree(new_frontend, frontend_src, dirs_exist_ok=True)
            _update_log("Copied new frontend/")
        elif os.path.isdir(new_frontend):
            if os.path.abspath(frontend_src) != os.path.abspath(
                os.path.join(backend_src, "frontend")
            ):
                shutil.copytree(new_frontend, frontend_src, dirs_exist_ok=True)
                _update_log("Copied new frontend/")

        shutil.rmtree(temp_dir, ignore_errors=True)
        _update_log("File copy complete.")

        # -- Step 3: Install dependencies --
        _update_log("--- Step 3: Installing Python dependencies ---")
        req_candidates = [
            os.path.join(os.path.dirname(__file__), "requirements.txt"),
            os.path.join(os.path.dirname(__file__), "..", "requirements.txt"),
        ]
        req_file = next((p for p in req_candidates if os.path.exists(p)), "")
        if os.path.exists(req_file):
            result = subprocess.run(
                ["pip", "install", "--no-cache-dir", "-q", "-r", req_file],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                _update_log("Dependencies installed successfully.")
            else:
                # pip failure is non-fatal - log warning and continue
                _update_log(
                    f"pip warning (non-fatal): {result.stderr.strip()[:400]}"
                )
        else:
            _update_log("No requirements.txt found, skipping.")

        # -- Step 4: Validate updated app --
        _update_log("--- Step 4: Validating updated app ---")
        _validate_runnable_app()
        _update_log("Updated app import validation passed.")

        # -- Step 5: Signal server reload --
        _update_log("--- Step 5: Signaling server reload ---")
        _update_log("Update complete! Restarting uvicorn in 3 seconds...")

        _update_status["state"] = "success"
        _update_status["finished_at"] = datetime.now(timezone.utc).isoformat()
        _update_status["error"] = None
        log_audit_event(
            username=actor,
            action="admin.docker.update.success",
            details=f"backup={backup_path}",
        )

        # Delay then restart uvicorn via os.execv to reload all modules
        def _restart_server():
            import time as _t

            _t.sleep(3)
            _update_log("Restarting server now...")
            _restart_uvicorn()

        threading.Thread(target=_restart_server, daemon=True).start()

    except Exception as exc:
        _update_log(f"ERROR: {exc}")
        _update_status["state"] = "error"
        _update_status["finished_at"] = datetime.now(timezone.utc).isoformat()
        _update_status["error"] = str(exc)
        log_audit_event(
            username=actor, action="admin.docker.update.failure", details=str(exc)
        )
    finally:
        # Ensure the update lock is always released
        try:
            _update_lock.release()
        except RuntimeError:
            pass  # Lock was not held (shouldn't happen, but be safe)


'''

# Replace the function
new_content = content[:start_idx] + new_function + content[start_idx + end_offset:]

with open(MAIN_PY, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Successfully replaced _do_update_in_thread function")
print(f"Old function size: {end_offset} chars")
print(f"New function size: {len(new_function)} chars")
