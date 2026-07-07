#!/usr/bin/env python
"""Obsidian vault sync helper for TrustSphere.

Talks to the Obsidian "Local REST API" plugin (HTTPS on 127.0.0.1:27124).
Only works WHILE THE OBSIDIAN APP IS OPEN.

This exists so any Claude session (CLI or app) can push updates to the vault with
one command instead of hand-writing the PowerShell TLS/cert workaround each time.

Usage (run with the backend venv python):
  python scripts/obsidian_sync.py check
  python scripts/obsidian_sync.py list                       # vault root
  python scripts/obsidian_sync.py list "Phases/"
  python scripts/obsidian_sync.py get  "Phases/Phase 5 - Security.md"
  python scripts/obsidian_sync.py put  "Phases/Phase 5 - Security.md" newcontent.md
  python scripts/obsidian_sync.py status "Phases/Phase 5 - Security.md" "✅ Done"
  python scripts/obsidian_sync.py check-tasks "Phases/Phase 5 - Security.md"   # tick all [ ] -> [x]

Config (env / backend/.env):
  OBSIDIAN_API_URL   default https://127.0.0.1:27124
  OBSIDIAN_API_KEY   required — set in backend/.env (not committed)
"""
import os
import re
import sys
import urllib.parse
from pathlib import Path

# Windows consoles default to cp1252 and choke on ✅/→ in status strings.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import requests
    import urllib3
    urllib3.disable_warnings()
except ImportError:
    sys.exit("requests not installed. Run: .\\venv\\Scripts\\python.exe -m pip install requests")

# dotenv resolves .env relative to the calling file, so point at backend/.env explicitly.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")
except ImportError:
    pass

BASE = os.getenv("OBSIDIAN_API_URL", "https://127.0.0.1:27124").rstrip("/")
KEY = os.getenv("OBSIDIAN_API_KEY", "")
if not KEY:
    sys.exit("OBSIDIAN_API_KEY is not set — add it to backend/.env")
HEADERS = {"Authorization": f"Bearer {KEY}"}
TIMEOUT = 6


def _url(vault_path: str) -> str:
    parts = [urllib.parse.quote(p) for p in vault_path.strip("/").split("/")]
    return f"{BASE}/vault/" + "/".join(parts)


def _die_offline(exc):
    sys.exit(
        "Obsidian is OFFLINE (could not reach the Local REST API).\n"
        "Open the Obsidian app (the vault 'TrustSphere AI'), then retry.\n"
        f"Detail: {exc}"
    )


def check():
    try:
        r = requests.get(f"{BASE}/", headers=HEADERS, verify=False, timeout=TIMEOUT)
    except Exception as e:
        _die_offline(e)
    if r.ok:
        print("Obsidian ONLINE and authenticated.")
    else:
        sys.exit(f"Reached server but got HTTP {r.status_code}: {r.text[:200]}")


def list_(folder: str = ""):
    url = f"{BASE}/vault/" + (urllib.parse.quote(folder.strip('/')) + "/" if folder else "")
    try:
        r = requests.get(url, headers=HEADERS, verify=False, timeout=TIMEOUT)
    except Exception as e:
        _die_offline(e)
    r.raise_for_status()
    for f in r.json().get("files", []):
        print(f)


def get(path: str) -> str:
    try:
        r = requests.get(_url(path), headers=HEADERS, verify=False, timeout=TIMEOUT)
    except Exception as e:
        _die_offline(e)
    if r.status_code == 404:
        sys.exit(f"Note not found: {path}")
    r.raise_for_status()
    return r.text


def put(path: str, content: str):
    headers = dict(HEADERS)
    headers["Content-Type"] = "text/markdown"
    try:
        r = requests.put(
            _url(path), headers=headers,
            data=content.encode("utf-8"), verify=False, timeout=TIMEOUT,
        )
    except Exception as e:
        _die_offline(e)
    if r.status_code not in (200, 204):
        sys.exit(f"PUT failed HTTP {r.status_code}: {r.text[:200]}")
    print(f"Updated: {path}")


def set_status(path: str, new_status: str):
    """Update both the frontmatter `status:` and the `**Status:**` line of a note."""
    content = get(path)
    # frontmatter:  status: "..."
    content, n1 = re.subn(
        r'(?m)^(status:\s*).*$', rf'\1"{new_status}"', content, count=1
    )
    # body:  **Status:** ...
    content, n2 = re.subn(
        r'(?m)^(\*\*Status:\*\*\s*).*$', rf'\g<1>{new_status}', content, count=1
    )
    if n1 == 0 and n2 == 0:
        sys.exit("No status field found to update in that note.")
    put(path, content)
    print(f"Status -> {new_status}  (frontmatter:{n1}, body:{n2})")


def check_tasks(path: str):
    """Tick every unchecked markdown task: '- [ ]' -> '- [x]'."""
    content = get(path)
    content, n = re.subn(r'(?m)^(\s*[-*]\s*)\[ \]', r'\1[x]', content)
    put(path, content)
    print(f"Checked off {n} task(s).")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    args = sys.argv[2:]
    if cmd == "check":
        check()
    elif cmd == "list":
        list_(args[0] if args else "")
    elif cmd == "get":
        print(get(args[0]))
    elif cmd == "put":
        # put <vault_path> <local_file>
        with open(args[1], "r", encoding="utf-8") as f:
            put(args[0], f.read())
    elif cmd == "status":
        set_status(args[0], args[1])
    elif cmd == "check-tasks":
        check_tasks(args[0])
    else:
        print(__doc__)
        sys.exit(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
