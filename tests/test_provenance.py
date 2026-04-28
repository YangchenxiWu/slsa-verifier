from __future__ import annotations

import hashlib
import json
from pathlib import Path

from slsa_verifier.provenance import build_provenance


def test_build_provenance_records_artifact_and_requirement_hashes(
    monkeypatch, tmp_path: Path
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "sample-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel-bytes")

    requirements = tmp_path / "requirements.txt"
    requirements.write_text("click==8.3.3\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_SHA", "deadbeef")

    provenance = build_provenance(dist)
    wheel_digest = hashlib.sha256(b"wheel-bytes").hexdigest()
    requirements_digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    wheel_key = "dist/sample-0.1.0-py3-none-any.whl"

    assert provenance["commit_sha"] == "deadbeef"
    assert provenance["artifact_sha256"][wheel_key] == wheel_digest
    assert provenance["artifacts"][wheel_key]["sha256"] == wheel_digest
    assert provenance["requirements_hash_summary"] == {
        "requirements.txt": {"sha256": requirements_digest}
    }

    expected_requirements_hash = hashlib.sha256(
        json.dumps(
            provenance["requirements_hash_summary"],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    assert provenance["requirements_hash"] == expected_requirements_hash
