from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_mapping(mapping: dict[str, dict[str, str]]) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode())
    return digest.hexdigest()


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def github_workflow_build_type() -> str:
    return "https://slsa-framework.github.io/github-actions-buildtypes/workflow/v1"


def github_builder_id() -> str:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return "https://github.com/actions/runner/github-hosted"
    return "https://example.com/build/local"


def build_provenance(dist: Path) -> dict[str, object]:
    requirements = sorted(Path(".").glob("requirements*.txt"))
    artifacts = sorted(
        path
        for pattern in ("*.whl", "*.tar.gz")
        for path in dist.glob(pattern)
        if path.is_file()
    )
    requirements_hash_summary = {
        display_path(path): {"sha256": sha256_file(path)} for path in requirements
    }
    artifact_sha256 = {display_path(path): sha256_file(path) for path in artifacts}
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    repository = os.environ.get("GITHUB_REPOSITORY")
    ref = os.environ.get("GITHUB_REF")
    workflow_ref = os.environ.get("GITHUB_WORKFLOW_REF")
    workflow_sha = os.environ.get("GITHUB_WORKFLOW_SHA")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    commit_sha = os.environ.get("GITHUB_SHA") or git_output("rev-parse", "HEAD")

    resolved_dependencies = []
    if repository and ref:
        resolved_dependencies.append(
            {
                "uri": f"git+{server_url}/{repository}@{ref}",
                "digest": {"gitCommit": commit_sha},
            }
        )
    resolved_dependencies.extend(
        {
            "name": display_path(path),
            "uri": f"file:{display_path(path)}",
            "digest": {"sha256": sha256_file(path)},
        }
        for path in requirements
    )

    return {
        "_type": "https://slsa.dev/provenance/v1",
        "buildDefinition": {
            "buildType": github_workflow_build_type(),
            "externalParameters": {
                "repository": repository,
                "ref": ref,
                "event": os.environ.get("GITHUB_EVENT_NAME"),
                "workflow": os.environ.get("GITHUB_WORKFLOW"),
                "workflow_ref": workflow_ref,
            },
            "internalParameters": {
                "github_run_id": os.environ.get("GITHUB_RUN_ID"),
                "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
                "github_job": os.environ.get("GITHUB_JOB"),
                "runner_os": os.environ.get("RUNNER_OS"),
                "runner_arch": os.environ.get("RUNNER_ARCH"),
            },
            "resolvedDependencies": resolved_dependencies,
        },
        "runDetails": {
            "builder": {
                "id": github_builder_id(),
                "version": {
                    "python": platform.python_version(),
                    "workflow_sha": workflow_sha or "",
                },
            },
            "metadata": {
                "invocationId": os.environ.get("GITHUB_RUN_ID") or commit_sha,
                "startedOn": timestamp,
                "finishedOn": timestamp,
            },
        },
        "commit_sha": commit_sha,
        "timestamp": timestamp,
        "artifact_sha256": artifact_sha256,
        "requirements_hash": sha256_mapping(requirements_hash_summary),
        "requirements_hash_summary": requirements_hash_summary,
        "artifacts": {
            display_path(path): {
                "sha256": artifact_sha256[display_path(path)],
                "size": path.stat().st_size,
            }
            for path in artifacts
        },
        "ci_environment": {
            "github_actions": os.environ.get("GITHUB_ACTIONS"),
            "ci": os.environ.get("CI"),
            "github_action": os.environ.get("GITHUB_ACTION"),
            "github_actor": os.environ.get("GITHUB_ACTOR"),
            "github_event_name": os.environ.get("GITHUB_EVENT_NAME"),
            "github_job": os.environ.get("GITHUB_JOB"),
            "github_ref": os.environ.get("GITHUB_REF"),
            "github_repository": os.environ.get("GITHUB_REPOSITORY"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_number": os.environ.get("GITHUB_RUN_NUMBER"),
            "github_server_url": os.environ.get("GITHUB_SERVER_URL"),
            "runner_arch": os.environ.get("RUNNER_ARCH"),
            "runner_name": os.environ.get("RUNNER_NAME"),
            "runner_os": os.environ.get("RUNNER_OS"),
            "python_version": platform.python_version(),
            "source_date_epoch": os.environ.get("SOURCE_DATE_EPOCH"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate CI provenance for built artifacts.")
    parser.add_argument("--dist", default="dist", help="Artifact directory.")
    parser.add_argument("--output", default="provenance.json", help="Provenance output path.")
    args = parser.parse_args()

    output = Path(args.output)
    provenance = build_provenance(Path(args.dist))
    output.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
