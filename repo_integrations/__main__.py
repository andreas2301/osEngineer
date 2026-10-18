"""Explicit provider reads only: `preflight` without --provider makes no remote calls."""
import argparse
import json
import subprocess
from pathlib import Path
from .client import IntegrationClient, IntegrationError, load_config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["doctor", "preflight"])
    parser.add_argument("--config", required=True, help="JSON configuration; credentials must be env references")
    parser.add_argument("--repo", help="Local checkout; resolves relative config paths and records local revision")
    parser.add_argument("--provider", action="append", default=[], help="Explicit provider to read; may repeat")
    args = parser.parse_args(argv)
    try:
        repo = Path(args.repo).resolve() if args.repo else None
        if repo is not None and not repo.is_dir():
            raise IntegrationError("Repository directory does not exist")
        config_path = Path(args.config)
        if repo and not config_path.is_absolute():
            config_path = repo / config_path
        client = IntegrationClient(load_config(config_path))
        report = client.doctor()
        report["evidence"] = []
        report["errors"] = []
        if repo:
            report["localHead"] = None
            try:
                run = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "HEAD"],
                                     capture_output=True, text=True, timeout=10, check=False)
                if run.returncode == 0:
                    report["localHead"] = run.stdout.strip()[:64]
            except (OSError, subprocess.TimeoutExpired):
                pass
        if args.command == "doctor" and args.provider:
            raise IntegrationError("doctor does not perform provider reads; use preflight")
        if args.command == "preflight":
            for provider in dict.fromkeys(args.provider):
                try:
                    report["evidence"].append(client.read(provider))
                except IntegrationError as exc:
                    report["errors"].append({"provider": provider if provider in client.config["providers"] else "unknown",
                                             "complete": False, "error": str(exc)})
        print(json.dumps(report, separators=(",", ":"), ensure_ascii=False))
        return 1 if report["errors"] or any(not row["complete"] for row in report["evidence"]) else 0
    except IntegrationError as exc:
        print(json.dumps({"schemaVersion": 1, "readOnly": True, "complete": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
