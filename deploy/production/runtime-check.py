"""Read-only production service, disk, and backup checks for scheduled monitoring."""
import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def service_failures(expected, containers):
    failures = []
    for service in expected:
        matches = [c for c in containers if c.get("Service") == service]
        if not matches:
            failures.append(f"{service}: container missing")
        for container in matches:
            if container.get("State") != "running":
                failures.append(f"{service}: not running")
            elif container.get("Health") not in (None, "", "healthy"):
                failures.append(f"{service}: health check not ready")
    return failures


def backup_failure(root, domain, max_age_hours, now=None):
    now = time.time() if now is None else now
    candidates = [p for p in root.glob(f"{domain}-*/SHA256SUMS") if p.is_file()]
    if not candidates:
        return "No completed backup manifest found"
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    if now - newest.stat().st_mtime > max_age_hours * 3600:
        return "Latest completed backup is overdue"
    if newest.stat().st_mtime > now + 300:
        return "Backup timestamp is in the future; check clock synchronization"
    try:
        directory = newest.parent.resolve()
        lines = newest.read_text().splitlines()
        if not lines:
            return "Completed backup has an empty checksum manifest"
        for line in lines:
            digest, separator, name = line.partition("  ")
            if not separator or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
                return "Completed backup has an invalid checksum manifest"
            target = (directory / name).resolve()
            if not target.is_relative_to(directory) or not target.is_file():
                return "Completed backup has a missing or unsafe archive path"
            checksum = hashlib.sha256()
            with target.open("rb") as archive:
                for block in iter(lambda: archive.read(1024 * 1024), b""):
                    checksum.update(block)
            if checksum.hexdigest() != digest.lower():
                return "Completed backup checksum does not match"
    except OSError:
        return "Completed backup could not be verified"
    return None


def worker_responded(replies):
    return isinstance(replies, dict) and any(
        isinstance(reply, dict) and reply.get("ok") == "pong"
        for reply in replies.values()
    )


def memory_failure(meminfo):
    values = {}
    for line in meminfo.splitlines():
        name, _, value = line.partition(":")
        if name in ("MemTotal", "MemAvailable"):
            values[name] = int(value.strip().split()[0])
    if values.get("MemTotal", 0) <= 0 or "MemAvailable" not in values:
        return "Host memory availability could not be checked"
    if values["MemAvailable"] / values["MemTotal"] < .10:
        return "Host has less than 10 percent available memory"
    return None


def docker_json(arguments):
    result = subprocess.run(["docker", *arguments], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError("Docker command failed; inspect Docker and Compose locally")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domains", nargs="+", required=True, help="Project domains whose backups must be fresh")
    parser.add_argument("--skip-public", action="store_true", help="Check services before DNS/TLS is configured")
    parser.add_argument("--backup-max-age-hours", type=float, default=26)
    args = parser.parse_args()
    if any(not domain or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in domain) or domain[0] == "-" for domain in args.domains):
        parser.error("Domains must contain lowercase letters, digits, and hyphens")
    if not math.isfinite(args.backup_max_age_hours) or args.backup_max_age_hours <= 0:
        parser.error("Backup maximum age must be positive")
    here = Path(__file__).resolve().parent
    compose = ["compose", "--project-directory", str(here), "-f", str(here / "compose.yaml")]
    failures = []
    try:
        config = docker_json([*compose, "config", "--format", "json"])
        containers = docker_json([*compose, "ps", "--all", "--format", "json"])
        if isinstance(containers, dict):
            containers = [containers]
        failures.extend(service_failures(config["services"], containers))
        if any(c.get("Service") == "celery" and c.get("State") == "running" for c in containers):
            try:
                replies = docker_json([*compose, "exec", "-T", "celery", "uv", "run", "celery", "-A", "corehq", "inspect", "--json", "--timeout", "10", "ping"])
                if not worker_responded(replies):
                    failures.append("Celery worker did not respond to its heartbeat")
            except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired):
                failures.append("Celery heartbeat could not complete")
        web = config["services"]["web"]
        minimum = int(web["environment"].get("COLLECTRA_MIN_FREE_DISK_GB", "10"))
        if minimum <= 0:
            raise ValueError("Disk safety margin must be positive")
        backup_root = next(Path(v["source"]) for v in web["volumes"] if v["target"] == "/backups")
        if not backup_root.is_dir():
            failures.append("Backup directory is missing")
        else:
            if shutil.disk_usage(backup_root).free < minimum * 1024 ** 3:
                failures.append("Data filesystem has insufficient free space")
            for domain in args.domains:
                error = backup_failure(backup_root, domain, args.backup_max_age_hours)
                if error:
                    failures.append(f"{domain}: {error}")
        docker_root = Path(docker_json(["info", "--format", "{{json .DockerRootDir}}"]))
        if not docker_root.is_dir():
            failures.append("Docker data filesystem could not be checked")
        elif shutil.disk_usage(docker_root).free < minimum * 1024 ** 3:
            failures.append("Docker data filesystem has insufficient free space")
        memory_error = memory_failure(Path("/proc/meminfo").read_text())
        if memory_error:
            failures.append(memory_error)
        if not args.skip_public:
            host = web["environment"]["COLLECTRA_HOST"]
            for path in ("/accounts/login/", "/formplayer/serverup"):
                try:
                    with urllib.request.urlopen(f"https://{host}{path}", timeout=30) as response:
                        if response.status != 200:
                            failures.append(f"Public endpoint failed: {path}")
                except Exception:
                    failures.append(f"Public HTTPS endpoint unreachable: {path}")
    except (RuntimeError, ValueError, KeyError, StopIteration, OSError, subprocess.TimeoutExpired):
        failures.append("Monitoring could not complete; inspect configuration and Docker locally")
    print(json.dumps({"ok": not failures, "failures": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
