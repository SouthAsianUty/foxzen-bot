#!/usr/bin/env python3
"""
🦊 Foxzen Bot - 1-Click Fast Live Sync to Hostinger VPS
Automatically uploads modified files and restarts the bot service on VPS in 2 seconds.
"""
import os
import sys
import time
from pathlib import Path
import paramiko

VPS_HOST = "200.141.10.244"
VPS_PORT = 22
VPS_USER = "root"
VPS_PASS = "Man#8028457#"
REMOTE_DIR = "/root/Foxzen_bot"

EXCLUDED_NAMES = {
    ".venv", "venv", ".git", "__pycache__", ".DS_Store",
    "bot_database.db", "foxzen_deploy.zip", ".idea", ".vscode"
}

def sync():
    local_root = Path(__file__).parent.resolve()
    print(f"🚀 Connecting to Hostinger VPS ({VPS_HOST})...")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(VPS_HOST, port=VPS_PORT, username=VPS_USER, password=VPS_PASS, timeout=12)
        sftp = ssh.open_sftp()
        print("✅ Connected via SSH/SFTP!")
    except Exception as e:
        print(f"❌ Failed to connect to VPS: {e}")
        return

    # Helper: Ensure remote dir exists
    def ensure_remote_dir(remote_path):
        dirs = []
        p = remote_path
        while p and p != "/":
            dirs.append(p)
            p = os.path.dirname(p)
        for d in reversed(dirs):
            try:
                sftp.stat(d)
            except IOError:
                try:
                    sftp.mkdir(d)
                except Exception:
                    pass

    # Collect files to sync
    files_to_sync = []
    for root, dirs, files in os.walk(local_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_NAMES and not d.startswith(".")]
        for f in files:
            if f in EXCLUDED_NAMES or f.endswith(".pyc") or f.startswith("."):
                continue
            local_file = Path(root) / f
            rel_path = local_file.relative_to(local_root).as_posix()
            files_to_sync.append((local_file, rel_path))

    print(f"🔍 Checking {len(files_to_sync)} project files for modifications...")
    uploaded_count = 0
    t0 = time.time()

    for local_file, rel_path in files_to_sync:
        remote_file = f"{REMOTE_DIR}/{rel_path}"
        local_stat = local_file.stat()
        local_mtime = int(local_stat.st_mtime)
        local_size = local_stat.st_size

        should_upload = False
        try:
            remote_stat = sftp.stat(remote_file)
            # If size differs or local is newer by > 1s
            if local_size != remote_stat.st_size or local_mtime > int(remote_stat.st_mtime) + 1:
                should_upload = True
        except IOError:
            # Remote file doesn't exist yet
            should_upload = True

        if should_upload:
            ensure_remote_dir(os.path.dirname(remote_file))
            print(f"  ⬆️ Uploading: {rel_path} ({local_size} bytes)")
            sftp.put(str(local_file), remote_file)
            sftp.utime(remote_file, (local_mtime, local_mtime))
            uploaded_count += 1

    sftp.close()
    elapsed = time.time() - t0

    if uploaded_count > 0:
        print(f"📦 Successfully synced {uploaded_count} modified file(s) in {elapsed:.2f}s!")
        print("🔄 Restarting Foxzen bot service on VPS...")
        stdin, stdout, stderr = ssh.exec_command("systemctl restart foxzen && systemctl status foxzen --no-pager | grep -E 'Active:|Main PID'")
        status_out = stdout.read().decode().strip()
        print(status_out)
        print(f"\n🎉 ALL CHANGES ARE LIVE ON VPS! (http://{VPS_HOST}:8000)")
    else:
        print(f"⚡ VPS is already up-to-date! No local changes detected ({elapsed:.2f}s).")

    ssh.close()

if __name__ == "__main__":
    sync()
