#!/usr/bin/env python3
"""Read a local intake folder and send stable files through authenticated LexFlow APIs."""
import argparse
import getpass
import hashlib
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
import httpx

SUPPORTED = {".txt", ".eml", ".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


class FolderAgent:
    def __init__(self, url, email, password, matter_id):
        parsed = urlsplit(url)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ("", "/")
                or parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1")):
            raise ValueError("Use an HTTPS origin or a loopback HTTP origin")
        self.client = httpx.Client(base_url=url.rstrip("/"), timeout=120, follow_redirects=False, trust_env=False)
        self.email, self.password, self.matter_id = email, password, matter_id
        self.csrf = ""
        self.max_bytes = 12 * 1024 * 1024

    def login(self):
        response = self.client.post("/api/auth/login", json={"email": self.email, "password": self.password})
        response.raise_for_status()
        result = response.json()
        if result.get("mfa_required"):
            code = getpass.getpass("Authenticator code or unused recovery code: ")
            response = self.client.post("/api/auth/mfa/verify", json={"challenge": result["challenge"], "code": code})
            response.raise_for_status()
            result = response.json()
        if result["user"].get("mfa_required") and not result["user"].get("mfa_enabled"):
            raise ValueError("Complete authenticator enrollment in the browser before using folder intake")
        self.csrf = result["csrf"]
        config = self.client.get("/api/config")
        config.raise_for_status()
        self.max_bytes = config.json()["max_upload_mb"] * 1024 * 1024

    def send(self, path):
        if path.is_symlink():
            return {"skipped": "symbolic link"}
        before = path.stat()
        if not before.st_size or before.st_size > self.max_bytes:
            return {"skipped": "empty or oversized file"}
        with path.open("rb") as stream:
            raw = stream.read(self.max_bytes + 1)
        after = path.stat()
        if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns or len(raw) > self.max_bytes:
            return {"skipped": "file changed during read"}
        digest = hashlib.sha256(self.matter_id.encode() + b"\0" + path.name.encode() + b"\0" + raw).hexdigest()
        for attempt in range(2):
            response = self.client.post("/api/integrations/intake", data={"matter_id": self.matter_id},
                files={"file": (path.name, raw)}, headers={"X-CSRF-Token": self.csrf, "Idempotency-Key": "folder-" + digest})
            if response.status_code == 401 and attempt == 0:
                self.login()
                continue
            response.raise_for_status()
            return response.json()

    def close(self):
        try:
            if self.csrf:
                self.client.post("/api/auth/logout", headers={"X-CSRF-Token": self.csrf})
        finally:
            self.client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--matter", required=True)
    parser.add_argument("--watch", action="store_true", help="Continue scanning every five seconds")
    args = parser.parse_args()
    folder = args.folder.expanduser().resolve()
    if not folder.is_dir():
        parser.error("Intake folder does not exist")
    password = os.getenv("LEXFLOW_AGENT_PASSWORD") or getpass.getpass("LexFlow password: ")
    agent = FolderAgent(args.url, args.email, password, args.matter)
    seen = set()
    try:
        agent.login()
        while True:
            for path in sorted(folder.iterdir()):
                if path.suffix.lower() not in SUPPORTED or path.is_symlink() or not path.is_file():
                    continue
                stat = path.stat()
                marker = (path.name, stat.st_size, stat.st_mtime_ns)
                if marker in seen:
                    continue
                try:
                    result = agent.send(path)
                    if result.get("skipped"):
                        print(f"Skipped {path.name}: {result['skipped']}")
                    else:
                        print(f"{'Already received' if result.get('replayed') else 'Received'}: {path.name}")
                        seen.add(marker)
                except httpx.HTTPStatusError as error:
                    print(f"Intake rejected: HTTP {error.response.status_code}; original file retained")
                except (httpx.HTTPError, OSError):
                    print("Intake could not complete; original file retained and the same key will be reused")
            if not args.watch:
                break
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        agent.close()


if __name__ == "__main__":
    main()
