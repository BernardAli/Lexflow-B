"""Operator commands: provision a dedicated office, snapshot, rotate artifacts, verify audit."""
import argparse
import getpass
import json
import os
from pathlib import Path
import uuid
import re
from .auth import hash_password, validate_password
from .db import db, initialize, record_audit, utcnow
from .exporter import DEFAULT_MAPPINGS
from .integrity import verify_integrity
from .settings import data_dir
from .storage import keyring, protect, reveal
from .snapshots import backup, restore, verify_snapshot


def provision(tenant, name, email, password):
    validate_password(password)
    with db(write=True) as conn:
        if conn.execute("SELECT 1 FROM tenants WHERE id=?", (tenant,)).fetchone():
            raise ValueError("Workspace already exists; provisioning does not overwrite accounts")
        conn.execute("INSERT INTO tenants VALUES(?,?,?)", (tenant, name, utcnow()))
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email.strip()):
            raise ValueError("Provide a valid administrator email")
        user_id = "admin-" + uuid.uuid4().hex
        conn.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?)", (user_id, tenant, email.strip().lower(), name + " Admin", "admin", hash_password(password), utcnow()))
        conn.executemany("INSERT INTO connector_mappings VALUES(?,?,?)", [(tenant, key, value) for key, value in DEFAULT_MAPPINGS.items()])
        record_audit(conn, tenant, None, user_id, "workspace_provisioned", {"deployment": "dedicated office"})


def rotate_artifacts(tenant):
    if not keyring(tenant):
        raise ValueError("Configure the workspace key ring before rotating artifacts")
    count = 0
    with db(write=True) as conn:
        paths = [row["file_path"] for table in ("documents", "exports") for row in conn.execute(f"SELECT file_path FROM {table} WHERE tenant_id=?", (tenant,))]
        for value in paths:
            path = Path(value).resolve()
            if not path.is_relative_to(data_dir()) or not path.is_file():
                raise ValueError("Artifact path is missing or outside the workspace data directory")
            encrypted = protect(reveal(path.read_bytes(), tenant, allow_legacy=True), tenant)
            temporary = path.with_name(path.name + ".rotating")
            try:
                with temporary.open("xb") as output:
                    os.chmod(temporary, 0o600)
                    output.write(encrypted)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
            count += 1
        record_audit(conn, tenant, None, None, "artifact_keys_rotated", {"files": count})
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-workspace")
    create.add_argument("--tenant-id", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--email", required=True)
    snap = sub.add_parser("backup")
    snap.add_argument("destination", type=Path)
    check = sub.add_parser("verify-backup")
    check.add_argument("source", type=Path)
    recover = sub.add_parser("restore")
    recover.add_argument("source", type=Path)
    recover.add_argument("destination", type=Path)
    pending = sub.add_parser("deliver-pending")
    pending.add_argument("--limit", type=int, default=20)
    for name in ("verify-audit", "rotate-artifacts"):
        command = sub.add_parser(name)
        command.add_argument("--tenant-id", required=True)
    args = parser.parse_args()
    if args.command == "verify-backup":
        print(json.dumps(verify_snapshot(args.source), indent=2))
        return
    if args.command == "restore":
        print(json.dumps(restore(args.source, args.destination), indent=2))
        return
    initialize()
    if args.command == "deliver-pending":
        from .security import validate_deployment
        from .demo_notary import start, stop
        from .delivery import resume_pending
        validate_deployment()
        destination = start()
        try:
            print(json.dumps(resume_pending(max(1, min(args.limit, 100))), indent=2))
        finally:
            stop(destination)
        return
    if args.command == "create-workspace":
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,64}", args.tenant_id):
            parser.error("Tenant ID must use 3–64 letters, digits, hyphens or underscores")
        password = getpass.getpass("New administrator password: ")
        if password != getpass.getpass("Confirm password: "):
            parser.error("Passwords do not match")
        provision(args.tenant_id, args.name, args.email, password)
        print("Workspace created. No demo accounts were added.")
    elif args.command == "backup":
        backup(args.destination)
        print("Snapshot created. Store the external signing/encryption keys separately and protect the backup volume.")
    elif args.command == "rotate-artifacts":
        print(f"Encrypted {rotate_artifacts(args.tenant_id)} artifacts using the first workspace key.")
    else:
        with db() as conn:
            result = verify_integrity(conn, args.tenant_id)
        print(json.dumps(result, indent=2))
        if not result["valid"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
