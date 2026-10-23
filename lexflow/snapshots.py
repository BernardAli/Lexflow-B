"""Authenticated, portable snapshots and verified restores to new directories."""
import hashlib
import hmac
import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from cryptography.fernet import Fernet

from .db import db, utcnow
from .integrity import audit_key, verify_integrity
from .settings import data_dir, database_path
from .storage import reveal


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def relative(path, root):
    value = Path(path)
    try:
        result = value.relative_to(root)
    except ValueError as exc:
        raise ValueError("Snapshot contains an artifact outside its declared data directory") from exc
    if result.is_absolute() or ".." in result.parts:
        raise ValueError("Snapshot artifact path is not safe")
    return result


def copy_database(source, target):
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as original:
        with closing(sqlite3.connect(target)) as copied:
            original.backup(copied)
            copied.commit()


def snapshot_key(root):
    configured = os.getenv("LEXFLOW_AUDIT_KEY")
    if configured:
        return configured.encode()
    path = root / ".audit-key"
    if not path.is_file() or path.is_symlink():
        raise ValueError("Provide the external audit key or the snapshot's protected local audit key")
    return path.read_bytes()


def backup(destination):
    source = data_dir()
    destination = Path(destination).expanduser().resolve()
    if destination.exists() or destination.is_relative_to(source):
        raise ValueError("Choose a new backup directory outside the active data directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".lexflow-backup-", dir=destination.parent))
    try:
        key = audit_key()
        with db(write=True):
            copy_database(database_path(), temporary / "lexflow.sqlite3")
            for name in ("uploads", "exports"):
                directory = source / name
                if directory.exists():
                    if directory.is_symlink() or any(path.is_symlink() for path in directory.rglob("*")):
                        raise ValueError("Snapshot artifacts must not contain symbolic links")
                    shutil.copytree(directory, temporary / name)
            for name in (".audit-key", ".mfa-key"):
                if os.getenv("LEXFLOW_AUDIT_KEY" if name == ".audit-key" else "LEXFLOW_MFA_KEY"):
                    continue
                if (source / name).exists():
                    if (source / name).is_symlink():
                        raise ValueError("Snapshot key files must not be symbolic links")
                    shutil.copy2(source / name, temporary / name)
            notary = source / "demo_notary"
            if notary.exists():
                if notary.is_symlink() or any(path.is_symlink() for path in notary.rglob("*")):
                    raise ValueError("The demo destination contains a symbolic link")
                copied_notary = temporary / "demo_notary"
                copied_notary.mkdir(mode=0o700)
                for path in notary.iterdir():
                    if path.name == "cases.sqlite3":
                        copy_database(path, copied_notary / path.name)
                    elif path.is_file() and not path.name.endswith(("-wal", "-shm")):
                        shutil.copy2(path, copied_notary / path.name)
            with closing(sqlite3.connect(temporary / "lexflow.sqlite3")) as conn:
                for table in ("documents", "exports"):
                    for identifier, path in conn.execute(f"SELECT id,file_path FROM {table}").fetchall():
                        rel = relative(path, source)
                        conn.execute(f"UPDATE {table} SET file_path=? WHERE id=?", (str(destination / rel), identifier))
                conn.commit()
        files = {path.relative_to(temporary).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in temporary.rglob("*") if path.is_file()}
        manifest = {"format": "lexflow-snapshot-v2", "created_at": utcnow(), "source_data_dir": str(source),
                    "snapshot_root": str(destination), "external_keys_included": False, "files": files,
                    "signing_key": "external" if os.getenv("LEXFLOW_AUDIT_KEY") else "included local demo key"}
        manifest["signature"] = hmac.new(key, canonical(manifest), hashlib.sha256).hexdigest()
        (temporary / "backup.json").write_text(json.dumps(manifest, indent=2))
        verify_snapshot(temporary)
        temporary.rename(destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def verify_snapshot(source):
    root = Path(source).expanduser().resolve()
    manifest_path = root / "backup.json"
    if not manifest_path.is_file() or manifest_path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Snapshot manifest is missing or too large")
    manifest = json.loads(manifest_path.read_text())
    signature = manifest.pop("signature", "")
    key = snapshot_key(root)
    if (manifest.get("format") != "lexflow-snapshot-v2" or not isinstance(signature, str)
            or not hmac.compare_digest(signature, hmac.new(key, canonical(manifest), hashlib.sha256).hexdigest())):
        raise ValueError("Snapshot manifest authentication failed; check the signing key")
    expected = manifest.get("files")
    if not isinstance(expected, dict) or "lexflow.sqlite3" not in expected:
        raise ValueError("Snapshot file manifest is invalid")
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Snapshot contains a symbolic link")
        if path.is_file() and path != manifest_path:
            name = path.relative_to(root).as_posix()
            actual.add(name)
            if expected.get(name) != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError("Snapshot file checksum failed: " + name)
    if actual != set(expected):
        raise ValueError("Snapshot contains missing or unexpected files")
    declared_root = Path(manifest["snapshot_root"])
    with closing(sqlite3.connect((root / "lexflow.sqlite3").as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or conn.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Snapshot database integrity failed")
        checkpoints = []
        for row in conn.execute("SELECT id FROM tenants"):
            verification = verify_integrity(conn, row[0], key=key)
            if not verification["valid"]:
                raise ValueError("Snapshot audit verification failed")
            checkpoints.append(verification["checkpoint"])
        artifacts = 0
        for table in ("documents", "exports"):
            for row in conn.execute(f"SELECT * FROM {table}"):
                path = root / relative(row["file_path"], declared_root)
                if not path.is_file():
                    raise ValueError("An artifact referenced by the database is missing")
                raw = reveal(path.read_bytes(), row["tenant_id"], allow_legacy=True)
                if table == "documents" and hashlib.sha256(raw).hexdigest() != row["sha256"]:
                    raise ValueError("Original-document authentication failed")
                artifacts += 1
        credentials = conn.execute("SELECT user_id,secret_ciphertext FROM mfa_credentials").fetchall()
        if credentials:
            configured = os.getenv("LEXFLOW_MFA_KEY")
            cipher = Fernet(configured.encode() if configured else (root / ".mfa-key").read_bytes())
            for row in credentials:
                value = json.loads(cipher.decrypt(row["secret_ciphertext"].encode()))
                if value.get("user_id") != row["user_id"]:
                    raise ValueError("Snapshot authenticator identity binding failed")
    notary = root / "demo_notary" / "cases.sqlite3"
    if notary.exists():
        cipher = Fernet((notary.parent / ".storage-key").read_bytes())
        with closing(sqlite3.connect(notary.as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Destination database integrity failed")
            for workspace, digest, encrypted in conn.execute("SELECT workspace_id,payload_sha256,payload_ciphertext FROM cases"):
                payload = json.loads(cipher.decrypt(encrypted))
                if payload.get("workspace_id") != workspace or hashlib.sha256(canonical(payload)).hexdigest() != digest:
                    raise ValueError("Destination case authentication failed")
    return {"valid": True, "format": manifest["format"], "files_checked": len(actual), "artifacts_checked": artifacts,
            "audit_checkpoints": checkpoints, "created_at": manifest["created_at"], "snapshot_root": manifest["snapshot_root"]}


def restore(source, destination):
    source = Path(source).expanduser().resolve()
    verified = verify_snapshot(source)
    destination = Path(destination).expanduser().resolve()
    if destination.exists() or destination.is_relative_to(source) or destination.is_relative_to(data_dir()):
        raise ValueError("Restore into a new directory outside the snapshot and active data directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".lexflow-restore-", dir=destination.parent))
    try:
        shutil.copytree(source, temporary, dirs_exist_ok=True)
        verify_snapshot(temporary)  # Verify the copied bytes before changing paths or sessions.
        with closing(sqlite3.connect(temporary / "lexflow.sqlite3")) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            for table in ("documents", "exports"):
                for identifier, value in conn.execute(f"SELECT id,file_path FROM {table}").fetchall():
                    conn.execute(f"UPDATE {table} SET file_path=? WHERE id=?", (str(destination / relative(value, Path(verified["snapshot_root"]))), identifier))
            conn.execute("DELETE FROM sessions")
            conn.execute("DELETE FROM password_resets")
            conn.execute("DELETE FROM mfa_challenges")
            conn.execute("UPDATE integration_jobs SET lease_until=0,lease_token=NULL")
            conn.commit()
        (temporary / "backup.json").rename(temporary / "restore-source-manifest.json")
        (temporary / "restore.json").write_text(json.dumps({"format": "lexflow-restore-v1", "restored_at": utcnow(),
            "verified_snapshot": verified, "sessions_revoked": True, "artifact_paths_rebased": True}, indent=2))
        temporary.rename(destination)
        return verified | {"restored_to": str(destination), "sessions_revoked": True}
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
